import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

# In prod, SECRET_KEY must already be set — base.py's _require_secret
# raises ImproperlyConfigured if missing (dev_fallback=False when DEBUG=False).

# Fail fast if ALLOWED_HOSTS is still the dev default in prod.
_prod_hosts = [h for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]  # noqa: F405
if not _prod_hosts:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must include real domain(s) in production. "
        "localhost/127.0.0.1 are not valid production hosts."
    )

# Production security toggles
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "1") in ("1", "true", "yes", "on")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(SECURE_HSTS_SECONDS)
SECURE_HSTS_PRELOAD = bool(SECURE_HSTS_SECONDS)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

