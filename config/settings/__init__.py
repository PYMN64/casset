"""Default settings module.

By default we use dev settings to keep local run simple.
In production set DJANGO_SETTINGS_MODULE=config.settings.prod
"""

from .dev import *  # noqa
