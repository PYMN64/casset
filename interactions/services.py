"""interactions/services.py — Business logic for comments/favorites.

Views call these functions; they never touch Comment/CommentLike/TrackFavorite
creation logic directly. Notification side-effects are NOT triggered here —
they're wired via signals (notifications/signals.py) on model post_save, so
this module only needs to worry about validation, permission, and the
toggle/create-or-delete dance.

Like/Follow (toggle_like, toggle_follow) predate this module and stayed
inline in views.py; not touched here to keep this change incremental.
"""

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from tracks.models import Track

from .models import Comment, CommentLike, TrackFavorite

logger = logging.getLogger("casset.interactions")

MAX_COMMENT_LENGTH = 1500


@dataclass
class CommentResult:
    ok: bool
    reason: str = ""
    comment: Comment | None = None


@dataclass
class ToggleResult:
    ok: bool
    reason: str = ""
    active: bool = False
    count: int = 0


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def _track_visible_to(track: Track, user) -> bool:
    """Same visibility rule as tracks.views.track_detail: owner always sees
    it; everyone else needs an APPROVED, non-PRIVATE track."""
    if user.is_authenticated and track.creator_id == user.id:
        return True
    return (
        track.status == Track.Status.APPROVED
        and track.visibility != Track.Visibility.PRIVATE
    )


def add_comment(*, author, track: Track, body: str) -> CommentResult:
    """Create a comment on a track. Never raises — returns a result object."""
    if not _track_visible_to(track, author):
        return CommentResult(ok=False, reason="not_found")

    if not track.allow_comments:
        return CommentResult(ok=False, reason="comments_disabled")

    body = (body or "").strip()
    if not body:
        return CommentResult(ok=False, reason="empty_body")
    if len(body) > MAX_COMMENT_LENGTH:
        return CommentResult(ok=False, reason="too_long")

    comment = Comment.objects.create(track=track, author=author, body=body)
    return CommentResult(ok=True, comment=comment)


def delete_comment(*, user, comment: Comment) -> CommentResult:
    """Delete a comment. Only the author or staff may delete."""
    if comment.author_id != user.id and not user.is_staff:
        return CommentResult(ok=False, reason="forbidden")
    comment.delete()
    return CommentResult(ok=True)


def toggle_comment_like(*, user, comment: Comment) -> ToggleResult:
    """Like/unlike a comment. Count is computed live (low-volume path,
    no cached counter field exists on Comment — avoids an extra migration
    for a number that's cheap to compute on this endpoint)."""
    if not comment.is_public or not _track_visible_to(comment.track, user):
        return ToggleResult(ok=False, reason="not_found")

    try:
        with transaction.atomic():
            CommentLike.objects.create(user=user, comment=comment)
        active = True
    except IntegrityError:
        with transaction.atomic():
            CommentLike.objects.filter(user=user, comment=comment).delete()
        active = False

    count = CommentLike.objects.filter(comment=comment).count()
    return ToggleResult(ok=True, active=active, count=count)


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

def toggle_favorite(*, user, track: Track) -> ToggleResult:
    if not _track_visible_to(track, user):
        return ToggleResult(ok=False, reason="not_found")

    try:
        with transaction.atomic():
            TrackFavorite.objects.create(user=user, track=track)
        active = True
    except IntegrityError:
        with transaction.atomic():
            TrackFavorite.objects.filter(user=user, track=track).delete()
        active = False

    count = TrackFavorite.objects.filter(track=track).count()
    return ToggleResult(ok=True, active=active, count=count)
