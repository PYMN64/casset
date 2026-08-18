"""
THIS FILE IS RETIRED — DO NOT USE.

The active settings split is:
  config/settings/base.py   — shared defaults
  config/settings/dev.py    — local development
  config/settings/prod.py   — production

DJANGO_SETTINGS_MODULE must point to one of the split modules, e.g.:
  config.settings.dev   (development)
  config.settings.prod  (production)

manage.py and pyproject.toml have been updated accordingly.
See .casset/state/changelog.md for the full migration note.
"""
raise ImportError(
    "config.settings is retired. "
    "Set DJANGO_SETTINGS_MODULE=config.settings.dev (or .prod) instead."
)

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# Runtime / security configuration
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in ("1", "true", "yes", "on")
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


# Cache (rate-limit / future analytics). Default: in-memory for local/test use.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "casset-locmem",
        }
    }


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "moderation",
    "accounts",
    "tracks",
    "plays",
    "playlists",
    "interactions",
    "explore",
    "subscriptions",
    "billing",
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
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database configuration.
# SQLite remains the zero-dependency local default; PostgreSQL can be selected
# through DB_ENGINE=postgresql without modifying application source code.
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
    raise ValueError("Unsupported DB_ENGINE. Use 'sqlite' or 'postgresql'.")


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "track_list"
LOGOUT_REDIRECT_URL = "track_list"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


PLAY_IP_SALT = os.getenv("PLAY_IP_SALT", "change-me-in-prod")
PLAY_UA_SALT = os.getenv("PLAY_UA_SALT", "change-me-in-prod")
PLAY_COUNT_AFTER_SECONDS = int(os.getenv("PLAY_COUNT_AFTER_SECONDS", "59"))
