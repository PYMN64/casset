"""notifications/models.py

Design principles
-----------------
* Append-only: notifications are never deleted, only marked as read.
* Polymorphic target: one model covers all event types via nullable FKs
  (track, actor, comment) + a JSON `extra` bag for future extensibility.
* Groupable: the `group_key` field lets the UI collapse N likes/follows
  into one notification row (e.g. "علی و ۳ نفر دیگر ترکت را لایک کردند").
* actor is nullable so system-generated notifications (track_approved,
  milestone_plays) work without a human sender.
"""

import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger("casset.notifications")


class Notification(models.Model):
    """One notification row for one recipient.

    Verb catalogue
    --------------
    new_follower          — someone followed you
    track_liked           — your track was liked
    track_comment         — someone commented on your track
    comment_liked         — your comment was liked
    track_approved        — staff approved your track
    track_rejected        — staff rejected your track
    new_track_from_follow — a creator you follow published a track
    milestone_plays       — your track hit 100/1000/… plays
    track_reposted        — someone reposted your track
    """

    class Verb(models.TextChoices):
        NEW_FOLLOWER          = "new_follower",          "فالوور جدید"
        TRACK_LIKED           = "track_liked",           "لایک ترک"
        TRACK_COMMENT         = "track_comment",         "کامنت جدید"
        COMMENT_LIKED         = "comment_liked",         "لایک کامنت"
        TRACK_APPROVED        = "track_approved",        "ترک تأیید شد"
        TRACK_REJECTED        = "track_rejected",        "ترک رد شد"
        NEW_TRACK_FROM_FOLLOW = "new_track_from_follow", "ترک جدید از کسی که دنبال می‌کنی"
        MILESTONE_PLAYS       = "milestone_plays",       "مایل‌ستون پخش"
        TRACK_REPOSTED        = "track_reposted",        "بازنشر ترک"

    # --- core fields ---
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    verb = models.CharField(max_length=32, choices=Verb.choices, db_index=True)

    # Human sender — null for system events (approve/reject/milestone)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )

    # --- polymorphic target FKs (all nullable) ---
    track = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    comment = models.ForeignKey(
        "interactions.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    # --- grouping ---
    # Notifications with the same group_key are collapsed in the UI.
    # Format: "<verb>:<target_type>:<target_id>"
    # e.g.  "track_liked:track:42"
    group_key = models.CharField(max_length=120, blank=True, db_index=True)

    # How many actors contributed to this grouped notification.
    # Updated in-place when a new event arrives for the same group_key.
    actor_count = models.PositiveIntegerField(default=1)

    # --- state ---
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # --- extensibility ---
    # Arbitrary JSON for verb-specific data (e.g. milestone value, reject reason).
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "created_at"],
                name="notif_recipient_read_ts",
            ),
            models.Index(
                fields=["group_key", "recipient"],
                name="notif_group_recipient",
            ),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return (
            f"Notif({self.verb}, "
            f"recipient={self.recipient_id}, "
            f"read={self.is_read})"
        )

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def mark_read(self) -> None:
        """Mark as read (idempotent)."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @classmethod
    def unread_count(cls, user) -> int:
        return cls.objects.filter(recipient=user, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user) -> int:
        """Mark all unread notifications for a user as read.

        Returns the number of rows updated.
        """
        now = timezone.now()
        return cls.objects.filter(recipient=user, is_read=False).update(
            is_read=True, read_at=now
        )

    # ------------------------------------------------------------------
    # Grouping helper
    # ------------------------------------------------------------------

    @staticmethod
    def build_group_key(verb: str, target_type: str, target_id: int) -> str:
        """Return a stable group key for collapsing related notifications."""
        return f"{verb}:{target_type}:{target_id}"

    def persian_text(self) -> str:
        """Return a human-readable Persian description for templates."""
        actor_name = (
            self.actor.profile.public_name()
            if self.actor and hasattr(self.actor, "profile")
            else "یک کاربر"
        )
        count = self.actor_count
        others = f"و {count - 1} نفر دیگر" if count > 1 else ""
        track_title = self.track.title if self.track else ""

        texts = {
            Notification.Verb.NEW_FOLLOWER: (
                f"{actor_name} {others} شما را دنبال کردند."
            ),
            Notification.Verb.TRACK_LIKED: (
                f"{actor_name} {others} «{track_title}» را لایک کردند."
            ),
            Notification.Verb.TRACK_COMMENT: (
                f"{actor_name} {others} روی «{track_title}» کامنت گذاشتند."
            ),
            Notification.Verb.COMMENT_LIKED: (
                f"{actor_name} {others} کامنت شما را لایک کردند."
            ),
            Notification.Verb.TRACK_APPROVED: (
                f"ترک «{track_title}» تأیید شد و منتشر گردید."
            ),
            Notification.Verb.TRACK_REJECTED: (
                f"ترک «{track_title}» رد شد. "
                f"{self.extra.get('reason', '')}"
            ),
            Notification.Verb.NEW_TRACK_FROM_FOLLOW: (
                f"{actor_name} ترک جدید «{track_title}» را منتشر کرد."
            ),
            Notification.Verb.MILESTONE_PLAYS: (
                f"ترک «{track_title}» به "
                f"{self.extra.get('milestone', '')} پخش رسید!"
            ),
            Notification.Verb.TRACK_REPOSTED: (
                f"{actor_name} {others} «{track_title}» را بازنشر کردند."
            ),
        }
        return texts.get(self.verb, self.get_verb_display())
