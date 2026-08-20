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

# Constitution (CLAUDE.md §2): production must run on PostgreSQL, never
# SQLite or a local filesystem-backed store. Fail fast rather than let a
# misconfigured DB_ENGINE silently boot prod on SQLite.
if DB_ENGINE != "postgresql":  # noqa: F405
    raise ImproperlyConfigured(
        f"Production requires DB_ENGINE=postgresql (got {DB_ENGINE!r}). "  # noqa: F405
        "SQLite is not a supported production database for Casset."
    )

if not DATABASES["default"].get("PASSWORD", "").strip():  # noqa: F405
    raise ImproperlyConfigured(
        "DB_PASSWORD environment variable is required but not set in production."
    )

# Default to enforcing TLS to the database unless the operator explicitly
# chose a different sslmode (e.g. a private VPC link where "disable" is
# acceptable). base.py defaults to "prefer", which silently allows an
# unencrypted connection — too permissive for prod.
if os.getenv("DB_SSLMODE") is None:
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"  # noqa: F405

# OTP login is the platform's only password-less entry point (accounts/
# views.py::phone_start_view) — it is worthless in production if no real SMS
# provider is configured, silently leaving users unable to receive a code.
# Fail fast rather than let that ship unnoticed, same fail-fast philosophy
# as the DB_ENGINE/DB_PASSWORD guards above.
if SMS_PROVIDER != "kavenegar":  # noqa: F405
    raise ImproperlyConfigured(
        f"Production requires SMS_PROVIDER=kavenegar (got {SMS_PROVIDER!r}). "  # noqa: F405
        "The 'console' provider only logs — it never sends a real SMS."
    )

if not KAVENEGAR_API_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "KAVENEGAR_API_KEY environment variable is required but not set in production."
    )

# Real money changes hands through this path — same fail-fast philosophy as
# everything above. "dev" never touches a real gateway, so it must never be
# reachable in production; same for a "zarinpal" selection without a real
# merchant ID (that would boot but 500 on every purchase attempt instead).
if PAYMENT_PROVIDER != "zarinpal":  # noqa: F405
    raise ImproperlyConfigured(
        f"Production requires PAYMENT_PROVIDER=zarinpal (got {PAYMENT_PROVIDER!r}). "  # noqa: F405
        "The 'dev' provider never charges real money."
    )

if not ZARINPAL_MERCHANT_ID:  # noqa: F405
    raise ImproperlyConfigured(
        "ZARINPAL_MERCHANT_ID environment variable is required but not set in production."
    )

# ---------------------------------------------------------------------------
# Object storage (media files) — S3-compatible (Arvan Cloud, Liara, MinIO,
# AWS S3, or anything else that speaks the S3 API). Constitution (CLAUDE.md
# §2): production must use object storage, not the local filesystem — a
# local MEDIA_ROOT doesn't survive a redeploy/restart on most hosting and
# can't be shared across multiple app instances. dev.py is untouched and
# keeps writing to disk.
#
# Kept opt-in (USE_S3_STORAGE) rather than unconditionally required so a
# first prod deploy can still boot before object storage is provisioned —
# unlike DB_ENGINE/SMS_PROVIDER, this isn't something every deploy needs on
# day one. When it IS turned on, the four S3_* vars below are mandatory.
# ---------------------------------------------------------------------------

USE_S3_STORAGE = os.getenv("USE_S3_STORAGE", "0") in ("1", "true", "yes", "on")

# Content-hashed static filenames.
#
# The service worker (static/sw.js) serves /static/ cache-first, which is
# only safe when a changed file gets a changed URL. With plain
# StaticFilesStorage a deploy would keep serving the previous CSS and JS
# from the visitor's cache until sw.js's own VERSION constant happened to
# be bumped — a manual step that will eventually be forgotten.
# ManifestStaticFilesStorage renames every asset by content hash at
# collectstatic time, so "cache it forever" and "ship an update" stop
# being in tension. Requires `collectstatic` before serving; a missing
# manifest entry then fails loudly instead of quietly serving stale bytes.
_STATICFILES_BACKEND = os.getenv(
    "DJANGO_STATICFILES_BACKEND",
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
)

if USE_S3_STORAGE:
    _required_s3_vars = ["S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET_NAME", "S3_ENDPOINT_URL"]
    _missing_s3_vars = [v for v in _required_s3_vars if not os.getenv(v, "").strip()]
    if _missing_s3_vars:
        raise ImproperlyConfigured(
            "USE_S3_STORAGE=1 but the following env vars are missing: "
            + ", ".join(_missing_s3_vars)
        )

    AWS_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY")
    AWS_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
    AWS_S3_REGION_NAME = os.getenv("S3_REGION", "").strip() or None
    # Providers like Arvan/Liara/MinIO don't reliably support per-object
    # ACLs the way AWS does — leave ACL unset and let the bucket's own
    # policy govern public read, rather than fail uploads on providers that
    # reject the ACL header outright.
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False
    _s3_custom_domain = os.getenv("S3_CUSTOM_DOMAIN", "").strip()
    if _s3_custom_domain:
        AWS_S3_CUSTOM_DOMAIN = _s3_custom_domain

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": _STATICFILES_BACKEND},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": _STATICFILES_BACKEND},
    }

# ---------------------------------------------------------------------------
# Error tracking — Sentry. Only initialized when SENTRY_DSN is set; a prod
# deploy without one still boots (this is operational nice-to-have, not a
# correctness requirement like DB/SMS/payment credentials above).
# ---------------------------------------------------------------------------

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
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

