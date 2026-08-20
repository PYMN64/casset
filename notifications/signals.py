"""notifications/signals.py — Django signal handlers that trigger notifications.

Every user action that should produce a notification is wired here.
This keeps notification logic out of views and models.

Each handler wraps its call in try/except so a notification bug
never breaks the primary action (like, follow, etc.).
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from interactions.models import Comment, CommentLike, CreatorFollow, Repost, TrackLike
from tracks.models import Track

logger = logging.getLogger("casset.notifications")


# ---------------------------------------------------------------------------
# Follow
# ---------------------------------------------------------------------------

@receiver(post_save, sender=CreatorFollow)
def on_follow(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_new_follower
        notify_new_follower(follower=instance.user, creator=instance.creator)
    except Exception as exc:
        logger.exception("on_follow signal error: %s", exc)


# ---------------------------------------------------------------------------
# Track like
# ---------------------------------------------------------------------------

@receiver(post_save, sender=TrackLike)
def on_track_liked(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_track_liked
        notify_track_liked(liker=instance.user, track=instance.track)
    except Exception as exc:
        logger.exception("on_track_liked signal error: %s", exc)


# ---------------------------------------------------------------------------
# Repost
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Repost)
def on_track_reposted(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_track_reposted
        notify_track_reposted(reposter=instance.user, track=instance.track)
    except Exception as exc:
        logger.exception("on_track_reposted signal error: %s", exc)


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Comment)
def on_comment_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_track_comment
        notify_track_comment(
            commenter=instance.author,
            track=instance.track,
            comment=instance,
        )
    except Exception as exc:
        logger.exception("on_comment_created signal error: %s", exc)


# ---------------------------------------------------------------------------
# Comment like
# ---------------------------------------------------------------------------

@receiver(post_save, sender=CommentLike)
def on_comment_liked(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from notifications.services import notify_comment_liked
        notify_comment_liked(liker=instance.user, comment=instance.comment)
    except Exception as exc:
        logger.exception("on_comment_liked signal error: %s", exc)


# ---------------------------------------------------------------------------
# Track status change (approved / rejected / published)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Track)
def on_track_status_changed(sender, instance, created, **kwargs):
    if created:
        return
    update_fields = kwargs.get("update_fields")
    if update_fields and "status" not in update_fields:
        return

    try:
        from notifications.services import notify_track_approved, notify_track_rejected
        from notifications.tasks import notify_new_track_to_followers_task
        if instance.status == Track.Status.APPROVED:
            notify_track_approved(track=instance)
            # Fan-out to followers only when newly approved + public — via
            # Celery now (see notifications/tasks.py), eager in dev/test.
            if instance.visibility == Track.Visibility.PUBLIC:
                notify_new_track_to_followers_task.delay(track_id=instance.id)

        elif instance.status == Track.Status.REJECTED:
            notify_track_rejected(
                track=instance,
                reason=instance.reject_reason or "",
            )
    except Exception as exc:
        logger.exception("on_track_status_changed signal error: %s", exc)
