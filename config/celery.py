"""Celery app instance.

Broker/result backend both point at REDIS_URL (already a project dependency
for caching — see config/settings/base.py). CELERY_TASK_ALWAYS_EAGER is set
in settings so dev/test runs execute tasks synchronously in-process without
needing a running worker or broker; prod requires a real worker
(`celery -A config worker`) since eager mode is off there.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("casset")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
