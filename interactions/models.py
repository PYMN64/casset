from django.conf import settings
from django.db import models


class TrackLike(models.Model):
    """A simple like on a Track."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="track_likes"
    )
    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "track"], name="uniq_like_user_track"
            )
        ]


class Repost(models.Model):
    """A user re-sharing someone else's track into their own followers'
    feed — distinct from Like (a private signal) and Favorite (a personal
    save list). Reposts are the organic-discovery engine on platforms like
    SoundCloud: they're what explore/services.py's feed logic should surface
    to a reposter's followers, same as new_track_from_follow does today."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reposts"
    )
    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="reposts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "track"], name="uniq_repost_user_track")
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="repost_user_created"),
        ]

    def __str__(self) -> str:
        return f"Repost(user={self.user_id}, track={self.track_id})"


class CreatorFollow(models.Model):
    """Follow relation between users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "creator"], name="uniq_follow_user_creator"
            )
        ]


class TrackFavorite(models.Model):
    """User saved (favorite) tracks."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "track"], name="uniq_fav_user_track"
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="fav_user_created"),
        ]


class Comment(models.Model):
    """Comments on tracks.

    Later we can generalize this to multiple content types, but Track-only keeps
    MVP stable and prevents migration churn.
    """

    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    body = models.TextField(max_length=1500)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["track", "created_at"], name="cmt_track_created"),
        ]

    def __str__(self) -> str:
        return f"Comment#{self.pk} track={self.track_id}"


class CommentLike(models.Model):
    """Likes for comments."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_likes"
    )
    comment = models.ForeignKey(
        "interactions.Comment", on_delete=models.CASCADE, related_name="likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "comment"], name="uniq_like_user_comment"
            )
        ]


class CreatorBlock(models.Model):
    """A creator blocking a specific user from commenting on the creator's
    own tracks. Scoped to the creator's tracks, not a platform-wide mute —
    matches the MVP goal: let a creator protect their own space without a
    full account-suspension decision (which is a staff-only action, see
    moderation.services.suspend_user)."""

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_commenters"
    )
    blocked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by_creators"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["creator", "blocked_user"], name="uniq_block_creator_blocked"
            )
        ]

    def __str__(self) -> str:
        return f"Block(creator={self.creator_id}, blocked={self.blocked_user_id})"
