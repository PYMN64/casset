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
LOGIN_REDIRECT_URL = "track_list"
LOGOUT_REDIRECT_URL = "track_list"

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
