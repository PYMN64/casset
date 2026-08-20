"""Google sign-in for Casset — OpenID Connect authorization-code flow.

Why this is hand-rolled rather than django-allauth
--------------------------------------------------
allauth brings ~40 provider packages, its own URL namespace, its own
templates, three extra models and a migration set, for one provider on a
site whose auth UI is entirely custom Persian markup. The flow below is
the whole of what we need — roughly 150 lines, no new dependency (it uses
`requests`, already present for the SMS and payment providers), and every
security decision is visible in this file instead of behind configuration.

Security notes
--------------
* PKCE (S256) is used even though this is a confidential client. It costs
  nothing and removes the entire class of authorization-code interception.
* `state` is a random value bound to the session; the callback rejects any
  response whose state does not match, which is what stops CSRF-style
  login-as-attacker forgeries.
* `nonce` is embedded in the auth request and must come back inside the ID
  token, which is what stops an ID token minted for another session being
  replayed at our callback.
* The ID token is NOT signature-verified locally, and that is deliberate:
  it arrives in the body of a direct, TLS-authenticated, server-to-server
  POST to Google's token endpoint, in response to a code only we hold.
  Google's own documentation calls signature validation unnecessary in
  exactly this case. Every *claim* is still validated below (iss, aud,
  exp, nonce, email_verified) — those checks are what actually matter.
* An unverified Google email is refused outright. Accepting one would let
  anyone who can create a Google account with an arbitrary unverified
  address take over the Casset account using that address.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("casset.security")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
VALID_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
SCOPES = "openid email profile"

#: How long a started flow stays valid. Long enough for a slow consent
#: screen, short enough that a stale session key cannot be reused later.
FLOW_TTL_SECONDS = 600

SESSION_KEY = "google_oauth_flow"


class GoogleAuthError(Exception):
    """Any failure that should send the user back to /login/ with a message."""


def is_configured() -> bool:
    """Whether Google sign-in should be offered at all.

    The button is hidden rather than shown-and-broken when credentials are
    missing, so a misconfigured deployment degrades to phone/password
    login instead of a dead end.
    """
    return bool(
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    )


def _require_config() -> tuple[str, str]:
    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        raise ImproperlyConfigured(
            "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET are not set."
        )
    return client_id, client_secret


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_authorization_url(request, *, redirect_uri: str, next_url: str = "") -> str:
    """Start a flow: stash state/nonce/verifier in the session, return the URL."""
    client_id, _ = _require_config()

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())

    request.session[SESSION_KEY] = {
        "state": state,
        "nonce": nonce,
        "verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "next": next_url,
        "started_at": int(time.time()),
    }
    request.session.modified = True

    from urllib.parse import urlencode

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # "select_account" instead of the default: a shared device should
        # not silently reuse whichever Google account is already signed in.
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def _pop_flow(request) -> dict:
    flow = request.session.pop(SESSION_KEY, None)
    request.session.modified = True
    if not flow:
        raise GoogleAuthError("no_flow")
    if int(time.time()) - int(flow.get("started_at", 0)) > FLOW_TTL_SECONDS:
        raise GoogleAuthError("expired")
    return flow


def _decode_id_token_payload(id_token: str) -> dict:
    """Return the ID token's claims.

    Signature is intentionally not checked here — see the module docstring
    for why that is safe in the authorization-code flow, and note that all
    the claims this returns are validated by the caller.
    """
    try:
        _, payload_b64, _ = id_token.split(".")
    except ValueError as exc:
        raise GoogleAuthError("malformed_id_token") from exc
    padding = "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise GoogleAuthError("malformed_id_token") from exc


def exchange_code(request, *, code: str, state: str) -> dict:
    """Complete a flow and return the verified Google identity.

    Returns a dict with: sub, email, name, picture.
    Raises GoogleAuthError on any validation failure.
    """
    client_id, client_secret = _require_config()
    flow = _pop_flow(request)

    # Constant-time compare: `state` is attacker-supplied.
    if not secrets.compare_digest(str(state or ""), str(flow.get("state", ""))):
        logger.warning("google_oauth: state mismatch")
        raise GoogleAuthError("state_mismatch")

    try:
        resp = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": flow["redirect_uri"],
                "grant_type": "authorization_code",
                "code_verifier": flow["verifier"],
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("google_oauth: token endpoint unreachable: %s", exc)
        raise GoogleAuthError("network") from exc

    if resp.status_code != 200:
        logger.warning("google_oauth: token exchange failed (%s)", resp.status_code)
        raise GoogleAuthError("token_exchange")

    id_token = (resp.json() or {}).get("id_token")
    if not id_token:
        raise GoogleAuthError("no_id_token")

    claims = _decode_id_token_payload(id_token)

    if claims.get("iss") not in VALID_ISSUERS:
        raise GoogleAuthError("bad_issuer")
    if claims.get("aud") != client_id:
        raise GoogleAuthError("bad_audience")
    if int(claims.get("exp", 0)) < int(time.time()):
        raise GoogleAuthError("expired_id_token")
    if not secrets.compare_digest(str(claims.get("nonce", "")), str(flow["nonce"])):
        raise GoogleAuthError("nonce_mismatch")

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("no_email")
    # Google reports this as a real bool or the string "true" depending on
    # the token; normalise before trusting it.
    verified = claims.get("email_verified")
    if verified not in (True, "true", "True"):
        raise GoogleAuthError("email_unverified")

    sub = claims.get("sub")
    if not sub:
        raise GoogleAuthError("no_subject")

    return {
        "sub": str(sub),
        "email": email,
        "name": (claims.get("name") or "").strip(),
        "picture": claims.get("picture") or "",
        "next": flow.get("next") or "",
    }
