"""
ASGI config for Casset.

DJANGO_SETTINGS_MODULE defaults to prod here because asgi.py is only
used in production deployments. Override via environment variable if needed.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
