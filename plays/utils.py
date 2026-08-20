import hashlib

from django.conf import settings


def get_client_ip(request) -> str:
    """Best-effort client IP for fraud-signal hashing.

    By default trusts only `REMOTE_ADDR` (the socket peer) — safe in any
    deployment, but collapses every visitor behind a reverse proxy/CDN to
    one IP. Set `TRUST_PROXY_HEADERS=1` (env) ONLY when Casset sits behind a
    reverse proxy/CDN you control that itself strips/overwrites any
    client-supplied `X-Forwarded-For` before forwarding — otherwise a
    visitor can simply send a spoofed header and defeat IP-based dedup/caps
    entirely, which is worse than the CDN-collapse problem this solves.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            # Leftmost entry is the original client per the de-facto
            # X-Forwarded-For convention; only meaningful if the proxy
            # itself is trusted to have set/sanitised this header.
            first = xff.split(",")[0].strip()
            if first:
                return first
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ip_hash(request) -> str:
    # salt سروری برای اینکه ip خام قابل بازیابی نباشه
    salt = getattr(settings, "PLAY_IP_SALT", settings.SECRET_KEY)
    ip = get_client_ip(request)
    return sha256_hex(f"{salt}|{ip}")


def ua_hash(request) -> str:
    salt = getattr(settings, "PLAY_UA_SALT", settings.SECRET_KEY)
    ua = request.META.get("HTTP_USER_AGENT") or ""
    return sha256_hex(f"{salt}|{ua}")
