from .base import *  # noqa

DEBUG = False

# Production security toggles
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "1") in ("1", "true", "yes", "on")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True if SECURE_HSTS_SECONDS else False
SECURE_HSTS_PRELOAD = True if SECURE_HSTS_SECONDS else False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

