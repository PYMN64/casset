"""Celery tasks for notifications.

Only notify_new_track_to_followers is async so far — the fan-out that used
to run synchronously in the request/signal path (see notifications/services.
py's docstring, now historical) and doesn't scale with follower count.
CELERY_TASK_ALWAYS_EAGER (config/settings/base.py) makes `.delay()` execute
in-process during dev/test — no separate worker needed to exercise this.
"""

from celery import shared_task


@shared_task(name="notifications.notify_new_track_to_followers")
def notify_new_track_to_followers_task(track_id: int) -> None:
    from tracks.models import Track

    from .services import notify_new_track_to_followers

    try:
        track = Track.objects.get(pk=track_id)
    except Track.DoesNotExist:
        return
    notify_new_track_to_followers(track=track)
