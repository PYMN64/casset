"""plays/geo.py — coarse, privacy-safe geography/device signals (S12).

Both signals are derived once, at request time, from data Casset already
collects for fraud-hashing (see plays/utils.py::ip_hash/ua_hash) — no new
data collection and no new user consent is introduced. Only the *derived,
coarse* value (a 2-letter country code, a device category) is ever
persisted (PlaybackSession.country_code/device_type) or returned by the
creator analytics API (plays/services.py::get_creator_geo_device_breakdown).
The raw client IP and the full User-Agent string never pass through this
module and are never stored unhashed anywhere in the codebase.

Country resolution deliberately does not add a GeoIP database/dependency:
it only trusts a country header set by a CDN/reverse-proxy already sitting
in front of Casset, and only when TRUST_PROXY_HEADERS=1 — the exact same
trust gate plays/utils.py::get_client_ip uses for X-Forwarded-For, for the
same reason (an untrusted proxy could otherwise spoof any header value).
Without a trusted proxy in front of Casset, country_code is simply left
empty ("unknown") rather than guessed.
"""

import re

from django.conf import settings

# Deliberately simple substring/regex checks, not a full UA-parsing library:
# "explainable, not ML" applies here too (see CLAUDE.md phase-2 plan §4.3).
_BOT_RE = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview", re.I)
_TABLET_HINT_RE = re.compile(r"iPad|Tablet|Nexus 7|Nexus 10|Kindle|Silk", re.I)
_MOBILE_HINT_RE = re.compile(r"Mobi|iPhone|iPod|Android", re.I)

# CDN/reverse-proxy headers that carry a GeoIP-resolved country. Only ever
# trusted when TRUST_PROXY_HEADERS is on — see module docstring.
_COUNTRY_HEADER_CANDIDATES = (
    "HTTP_CF_IPCOUNTRY",    # Cloudflare
    "HTTP_X_COUNTRY_CODE",  # Arvan Cloud / generic CDN convention
    "HTTP_X_GEO_COUNTRY",
)


def resolve_device_type(user_agent: str) -> str:
    """Classify a User-Agent string into a coarse device category.

    Takes the raw string (already in hand at request time, before it gets
    hashed for ua_hash) — never stores it, only returns one of a handful of
    fixed category codes.
    """
    from .models import PlaybackSession

    ua = (user_agent or "").strip()
    if not ua:
        return PlaybackSession.DeviceType.UNKNOWN
    if _BOT_RE.search(ua):
        return PlaybackSession.DeviceType.BOT
    if _TABLET_HINT_RE.search(ua) or ("Android" in ua and "Mobile" not in ua):
        return PlaybackSession.DeviceType.TABLET
    if _MOBILE_HINT_RE.search(ua):
        return PlaybackSession.DeviceType.MOBILE
    return PlaybackSession.DeviceType.DESKTOP


def resolve_country_code(request) -> str:
    """Best-effort 2-letter country code from a trusted CDN geo header.

    Returns "" (unknown) unless TRUST_PROXY_HEADERS is enabled AND one of
    the known headers is present with a plausible 2-letter value — the same
    conservative default as plays/utils.py::get_client_ip.
    """
    if not getattr(settings, "TRUST_PROXY_HEADERS", False):
        return ""
    for header in _COUNTRY_HEADER_CANDIDATES:
        value = (request.META.get(header) or "").strip().upper()
        if len(value) == 2 and value.isalpha():
            return value
    return ""
