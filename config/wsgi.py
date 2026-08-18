"""
WSGI config for Casset.

DJANGO_SETTINGS_MODULE defaults to prod here because wsgi.py is only
used in production deployments. Override via environment variable if needed.
"""

import os

from django.core.wsgi import get_wsgi_application

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
