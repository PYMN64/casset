"""Base settings for Casset.

Split settings modules:
- config.settings.dev  (local development — DJANGO_SETTINGS_MODULE=config.settings.dev)
- config.settings.prod (production        — DJANGO_SETTINGS_MODULE=config.settings.prod)

Security contract
-----------------
* SECRET_KEY, PLAY_IP_SALT, PLAY_UA_SALT are **required** in production.
  If any is missing, startup fails with an explicit ImproperlyConfigured.
* In development (DEBUG=True) a safe random fallback is generated at
  startup so developers don't need a .env file to run locally.
* The insecure hardcoded string 'django-insecure-*' / 'change-me-in-prod'
  can NEVER appear as a runtime value again.
"""

import os
import secrets
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_secret(env_var: str, *, dev_fallback: bool = False) -> str:
    """Return the value of *env_var* or raise ImproperlyConfigured.

    When *dev_fallback* is True (only used for non-production contexts) a
    cryptographically random value is generated and a loud warning is printed
    so developers know they should set the variable.
    """
    value = os.getenv(env_var, "").strip()
    if value:
        return value
    if dev_fallback:
        generated = secrets.token_hex(48)
        import warnings
        warnings.warn(
            f"\n{'='*70}\n"
            f"  {env_var} is not set. "
            f"A random value was generated for this session.\n"
            f"  Set {env_var} in your .env file to make it persistent.\n"
            f"{'='*70}",
            stacklevel=2,
        )
        return generated
    raise ImproperlyConfigured(
        f"{env_var} environment variable is required but not set. "
        f"Add it to your .env file or deployment secrets."
    )


# ---------------------------------------------------------------------------
# DEBUG — must be resolved before _require_secret so dev_fallback works
# ---------------------------------------------------------------------------

DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in ("1", "true", "yes", "on")

# ---------------------------------------------------------------------------
# Security-critical secrets
# ---------------------------------------------------------------------------

# In dev: auto-generate if missing (session-scoped, printed as warning).
# In prod: fail fast if missing — no silent insecure fallback ever.
SECRET_KEY = _require_secret("DJANGO_SECRET_KEY", dev_fallback=DEBUG)
PLAY_IP_SALT = _require_secret("PLAY_IP_SALT", dev_fallback=DEBUG)
PLAY_UA_SALT = _require_secret("PLAY_UA_SALT", dev_fallback=DEBUG)

# Only set this to true when Casset sits behind a reverse proxy/CDN you
# control that strips/overwrites any client-supplied X-Forwarded-For before
# forwarding — see plays/utils.py::get_client_ip. Off by default: trusting
# this header from an untrusted source lets any visitor spoof their IP for
# fraud-signal purposes, which is worse than the single-IP-behind-CDN
# problem it's meant to solve.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"

# ---------------------------------------------------------------------------
# Hosts / CSRF
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",

    "rest_framework",
    "django_filters",

    "core",
    "accounts.apps.AccountsConfig",
    "tracks",
    "uploads",
    "plays",
    "interactions",
    "playlists",
    "explore",
    "moderation",
    "billing",
    "notifications",
    # NOTE: 'subscriptions' is RETIRED — lives in _deprecated/, never re-add.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.OnboardingRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.platform_settings",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — SQLite default for local dev; Postgres via env for prod
# ---------------------------------------------------------------------------

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "casset"),
            "USER": os.getenv("DB_USER", "casset"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            # Pairs with CONN_MAX_AGE: probes a pooled connection before
            # reuse so a connection killed server-side (idle timeout,
            # managed-Postgres failover) doesn't surface as a request error.
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                # "prefer" negotiates TLS when the server offers it and
                # silently falls back otherwise — safe for local/dev
                # Postgres. prod.py raises this to "require".
                "sslmode": os.getenv("DB_SSLMODE", "prefer").strip().lower(),
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
            },
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("DB_NAME", "db.sqlite3"),
        }
    }
else:
    raise ImproperlyConfigured(
        f"Unsupported DB_ENGINE={DB_ENGINE!r}. Use 'sqlite' or 'postgresql'."
    )

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# AllowAllUsersModelBackend (not the default ModelBackend): the default
# backend silently folds "wrong password" and "suspended account" into the
# same generic error, because it refuses to even return a User object for
# an inactive account — AuthenticationForm.confirm_login_allowed() (where
# accounts.forms.LoginForm's clear "این حساب تعلیق شده است" message lives)
# never gets a user to check. This backend still authenticates by password
# first; confirm_login_allowed() is what actually blocks the inactive user,
# same enforcement, better message.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.AllowAllUsersModelBackend"]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------

LOGIN_URL = "login"
# Discover, not the flat track list: signing in should land a listener on
# the page the product is actually built around.
LOGIN_REDIRECT_URL = "discover"
LOGOUT_REDIRECT_URL = "discover"

# ---------------------------------------------------------------------------
# Cache — Redis if available, in-memory fallback
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "casset-locmem",
        }
    }

# ---------------------------------------------------------------------------
# Play anti-fraud
# ---------------------------------------------------------------------------

PLAY_COUNT_AFTER_SECONDS = int(os.getenv("PLAY_COUNT_AFTER_SECONDS", "59"))

# ---------------------------------------------------------------------------
# SMS (OTP delivery) — see accounts/services.py for the provider abstraction.
# "console" (dev/test default) only logs; "kavenegar" sends real SMS.
# prod.py fails fast if SMS_PROVIDER != "kavenegar" or the API key is empty.
# ---------------------------------------------------------------------------

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console").strip().lower()
KAVENEGAR_API_KEY = os.getenv("KAVENEGAR_API_KEY", "").strip()
KAVENEGAR_SENDER = os.getenv("KAVENEGAR_SENDER", "").strip()

# ---------------------------------------------------------------------------
# Google sign-in (OpenID Connect) — see accounts/oauth.py.
#
# Optional by design: with these unset the Google button is hidden and
# phone/password sign-in still works, so a deployment without Google
# credentials degrades gracefully instead of showing a dead button. That is
# why there is no prod fail-fast guard here, unlike SMS and payments, which
# the product genuinely cannot run without.
# ---------------------------------------------------------------------------

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

# ---------------------------------------------------------------------------
# Payment gateway — see billing/services.py for the provider abstraction.
# "dev" (default) never touches a real gateway; "zarinpal" does. prod.py
# fails fast if PAYMENT_PROVIDER != "zarinpal" or the merchant ID is empty.
# ---------------------------------------------------------------------------

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "dev").strip().lower()
ZARINPAL_MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID", "").strip()
ZARINPAL_SANDBOX = os.getenv("ZARINPAL_SANDBOX", "0") in ("1", "true", "yes", "on")

# ---------------------------------------------------------------------------
# Celery — broker/result backend share REDIS_URL with the cache above.
# CELERY_TASK_ALWAYS_EAGER defaults True: without a REDIS_URL (the common
# dev/CI case, per pyproject.toml's default DJANGO_SETTINGS_MODULE=dev) or a
# running worker, tasks would otherwise just queue forever and never run.
# Eager mode makes `.delay()` execute synchronously in-process instead —
# same call sites, no behavior difference for tests. prod.py sets this False
# so notification fan-out actually goes through a real worker at scale.
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or None
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "1" if not REDIS_URL else "0") in (
    "1", "true", "yes", "on",
)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Periodic tasks (needs a separate `celery -A config beat` process in prod;
# CELERY_TASK_ALWAYS_EAGER dev/test doesn't run these on a schedule at all —
# call the task function directly in a shell/test instead).
CELERY_BEAT_SCHEDULE = {
    "creator-weekly-digest": {
        "task": "notifications.send_creator_weekly_digest",
        "schedule": crontab(day_of_week="monday", hour=6, minute=0),  # 09:30 Asia/Tehran-ish
    },
}

# ---------------------------------------------------------------------------
# Email — used only for the creator weekly digest so far (notifications/
# tasks.py). Falls back to the console backend (logs, no real send) when
# EMAIL_HOST is empty, same non-blocking posture as Sentry: this is a
# retention nice-to-have, not correctness-critical infra like SMS/payment,
# so it doesn't get a prod fail-fast guard.
# ---------------------------------------------------------------------------

EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") in ("1", "true", "yes", "on")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Casset <no-reply@casset.ir>")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "casset.plays":    {"handlers": ["console"], "level": "INFO", "propagate": False},
        "casset.uploads":  {"handlers": ["console"], "level": "INFO", "propagate": False},
        "casset.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ]
}
