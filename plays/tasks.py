"""Celery tasks for plays — the scheduled DailyTrackStat aggregation
(config/settings/base.py::CELERY_BEAT_SCHEDULE). CELERY_TASK_ALWAYS_EAGER
makes `.delay()` run in-process during dev/test; the beat schedule itself
only fires with a real `celery -A config beat` process, so call
aggregate_daily_stats() directly in a shell/test to exercise it outside
that schedule (see notifications/tasks.py for the same pattern).
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("casset.plays")


@shared_task(name="plays.aggregate_yesterday_track_stats")
def aggregate_yesterday_track_stats() -> int:
    """Roll PlayEvent into DailyTrackStat for the day that just ended.
    Idempotent (aggregate_daily_stats upserts), so a retried/duplicate run
    is harmless."""
    from .services import aggregate_daily_stats

    yesterday = timezone.localdate() - timedelta(days=1)
    written = aggregate_daily_stats(yesterday)
    logger.info("aggregate_yesterday_track_stats: day=%s tracks=%d", yesterday, written)
    return written
