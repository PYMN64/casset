"""Celery tasks for notifications — the async fan-out plus the scheduled
weekly creator digest (config/settings/base.py::CELERY_BEAT_SCHEDULE).
CELERY_TASK_ALWAYS_EAGER makes `.delay()` execute in-process during
dev/test — no separate worker needed to exercise either task; the beat
schedule itself only fires with a real `celery -A config beat` process,
so call send_creator_weekly_digest() directly in a shell/test to exercise it
outside that schedule.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger("casset.notifications")


@shared_task(name="notifications.notify_new_track_to_followers")
def notify_new_track_to_followers_task(track_id: int) -> None:
    from tracks.models import Track

    from .services import notify_new_track_to_followers

    try:
        track = Track.objects.get(pk=track_id)
    except Track.DoesNotExist:
        return
    notify_new_track_to_followers(track=track)


@shared_task(name="notifications.send_creator_weekly_digest")
def send_creator_weekly_digest() -> int:
    """Email each active creator a one-week activity summary (plays, new
    followers). Skips creators with nothing to report — an empty "0 plays
    this week" email trains people to ignore the digest entirely, which
    defeats the point of a retention email. Returns the number sent."""
    from accounts.models import UserProfile
    from interactions.models import CreatorFollow
    from plays.models import PlayEvent
    from tracks.models import Track

    since = timezone.now() - timedelta(days=7)
    sent = 0

    creators = (
        UserProfile.objects.filter(creator_status=UserProfile.CreatorStatus.APPROVED)
        .exclude(user__email="")
        .select_related("user")
    )

    for profile in creators:
        user = profile.user
        track_ids = list(Track.objects.filter(creator=user).values_list("id", flat=True))
        if not track_ids:
            continue

        plays = PlayEvent.objects.filter(track_id__in=track_ids, created_at__gte=since).count()
        new_followers = CreatorFollow.objects.filter(creator=user, created_at__gte=since).count()
        if plays == 0 and new_followers == 0:
            continue

        subject = "خلاصه هفتگی فعالیت شما در Casset"
        body = (
            f"سلام {profile.public_name()}،\n\n"
            f"این هفته روی محتوای تو:\n"
            f"  • {plays} پخش جدید\n"
            f"  • {new_followers} دنبال‌کننده‌ی جدید\n\n"
            f"برای جزئیات کامل، به استودیوی خودت سر بزن.\n"
        )
        try:
            send_mail(subject, body, None, [user.email], fail_silently=False)
            sent += 1
        except Exception:
            logger.exception("send_creator_weekly_digest: failed for user=%s", user.id)

    logger.info("send_creator_weekly_digest: sent=%d", sent)
    return sent
