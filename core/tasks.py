"""Celery tasks for core — the scheduled database backup
(config/settings/base.py::CELERY_BEAT_SCHEDULE). CELERY_TASK_ALWAYS_EAGER
makes `.delay()` execute in-process during dev/test, same as
notifications/tasks.py; the beat schedule itself only fires with a real
`celery -A config beat` process, so call backup_database_task() directly in
a shell/test to exercise it outside that schedule.
"""

import logging

from celery import shared_task

from .backup import BackupError, run_database_backup

logger = logging.getLogger("casset.core")


@shared_task(name="core.backup_database")
def backup_database_task() -> dict:
    """Run a full database backup and upload it to object storage.

    Re-raises on failure rather than catching it: a scheduled Celery task
    that raises is recorded as FAILED and surfaces in monitoring/Sentry —
    exactly what a silently-broken backup schedule must not be able to hide
    behind.
    """
    try:
        result = run_database_backup(upload=True)
    except BackupError:
        logger.exception("backup_database_task: backup failed")
        raise

    logger.info(
        "backup_database_task: ok filename=%s size_bytes=%d storage_path=%s",
        result["filename"], result["size_bytes"], result["storage_path"],
    )
    return result
