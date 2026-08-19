import hashlib

from django.conf import settings


def get_client_ip(request) -> str:
    # MVP: مستقیم. بعداً اگر پشت CDN بودیم، X-Forwarded-For رو با دقت اضافه می‌کنیم.
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
