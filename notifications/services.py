"""notifications/services.py — Notification creation logic.

All notification creation goes through this module.
Views and signal handlers call these functions; they never
touch Notification directly.

Grouping strategy
-----------------
When multiple actors trigger the same verb on the same target
(e.g. 5 users like track #42), we update ONE notification row
instead of inserting 5 rows. The recipient sees:
  "علی و ۴ نفر دیگر ترک شما را لایک کردند."

The group window is 24 hours. After that a new row is created.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("casset.notifications")

PLAY_MILESTONES = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]
_GROUP_WINDOW = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def notify_new_follower(*, follower, creator) -> None:
    """Notify creator that follower started following them."""
    if follower.pk == creator.pk:
        return
    _upsert(
        recipient=creator,
        verb="new_follower",
        actor=follower,
        group_key=_gkey("new_follower", "user", creator.pk),
    )


def notify_track_liked(*, liker, track) -> None:
    """Notify track creator that someone liked their track."""
    creator = track.creator
    if liker.pk == creator.pk:
        return
    _upsert(
        recipient=creator,
        verb="track_liked",
        actor=liker,
        track=track,
        group_key=_gkey("track_liked", "track", track.pk),
    )


def notify_track_comment(*, commenter, track, comment) -> None:
    """Notify track creator that someone commented."""
    creator = track.creator
    if commenter.pk == creator.pk:
        return
    _upsert(
        recipient=creator,
        verb="track_comment",
        actor=commenter,
        track=track,
        comment=comment,
        group_key=_gkey("track_comment", "track", track.pk),
    )


def notify_comment_liked(*, liker, comment) -> None:
    """Notify comment author that someone liked their comment."""
    author = comment.author
    if liker.pk == author.pk:
        return
    _upsert(
        recipient=author,
        verb="comment_liked",
        actor=liker,
        track=comment.track,
        comment=comment,
        group_key=_gkey("comment_liked", "comment", comment.pk),
    )


def notify_track_approved(*, track) -> None:
    """System notification: track was approved by staff."""
    _create_system(recipient=track.creator, verb="track_approved", track=track)


def notify_track_rejected(*, track, reason: str = "") -> None:
    """System notification: track was rejected by staff."""
    _create_system(
        recipient=track.creator,
        verb="track_rejected",
        track=track,
        extra={"reason": reason},
    )


def notify_new_track_to_followers(*, track) -> None:
    """Fan-out: notify each follower of creator about a new public track.

    Runs synchronously for MVP. Move to Celery for large follower counts.
    """
    from interactions.models import CreatorFollow
    from .models import Notification

    creator = track.creator
    follower_ids = list(
        CreatorFollow.objects.filter(creator=creator)
        .values_list("user_id", flat=True)
    )
    if not follower_ids:
        return

    batch = [
        Notification(
            recipient_id=fid,
            verb=Notification.Verb.NEW_TRACK_FROM_FOLLOW,
            actor=creator,
            track=track,
            group_key=_gkey("new_track_from_follow", "track", track.pk),
            extra={},
        )
        for fid in follower_ids
        if fid != creator.pk
    ]
    if batch:
        Notification.objects.bulk_create(batch, ignore_conflicts=True)
        logger.info(
            "notify_new_track: track=%s → %d followers", track.pk, len(batch)
        )


def check_and_notify_milestone(*, track) -> None:
    """Idempotent milestone check — safe to call on every play register."""
    from .models import Notification

    for milestone in PLAY_MILESTONES:
        if track.play_count < milestone:
            break
        already = Notification.objects.filter(
            recipient=track.creator,
            verb=Notification.Verb.MILESTONE_PLAYS,
            track=track,
            extra__milestone=milestone,
        ).exists()
        if not already:
            _create_system(
                recipient=track.creator,
                verb="milestone_plays",
                track=track,
                extra={"milestone": milestone},
            )
            logger.info(
                "milestone_plays: track=%s milestone=%d", track.pk, milestone
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gkey(verb: str, target_type: str, target_id: int) -> str:
    return f"{verb}:{target_type}:{target_id}"


def _upsert(
    *, recipient, verb, actor, group_key,
    track=None, comment=None, extra=None,
) -> None:
    """Create or update a grouped notification within the group window."""
    from .models import Notification

    window_start = timezone.now() - _GROUP_WINDOW
    with transaction.atomic():
        existing = (
            Notification.objects
            .select_for_update()
            .filter(
                recipient=recipient,
                verb=verb,
                group_key=group_key,
                is_read=False,
                created_at__gte=window_start,
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            existing.actor_count += 1
            existing.actor = actor
            existing.is_read = False
            existing.read_at = None
            existing.updated_at = timezone.now()
            existing.save(update_fields=[
                "actor_id", "actor_count", "is_read", "read_at", "updated_at",
            ])
        else:
            Notification.objects.create(
                recipient=recipient,
                verb=verb,
                actor=actor,
                track=track,
                comment=comment,
                group_key=group_key,
                actor_count=1,
                extra=extra or {},
            )


def _create_system(*, recipient, verb, track=None, extra=None) -> None:
    """Create a system notification (no actor, no grouping)."""
    from .models import Notification

    Notification.objects.create(
        recipient=recipient,
        verb=verb,
        actor=None,
        track=track,
        group_key="",
        extra=extra or {},
    )
    logger.info(
        "system notif: verb=%s recipient=%s track=%s",
        verb, recipient.pk, track.pk if track else None,
    )
