from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from tracks.models import Track

from . import services
from .models import Comment, CreatorFollow, TrackLike

User = get_user_model()


@require_POST
def toggle_like(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    if not track_id or not str(track_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    track = Track.objects.filter(id=int(track_id), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC).first()
    if not track:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    liked = False
    try:
        with transaction.atomic():
            TrackLike.objects.create(user=request.user, track=track)
            Track.objects.filter(id=track.id).update(like_count=F("like_count") + 1)
            liked = True
    except IntegrityError:
        with transaction.atomic():
            TrackLike.objects.filter(user=request.user, track=track).delete()
            Track.objects.filter(id=track.id, like_count__gt=0).update(like_count=F("like_count") - 1)
            liked = False

    track.refresh_from_db(fields=["like_count"])
    return JsonResponse({"ok": True, "liked": liked, "like_count": track.like_count})


@require_POST
def toggle_follow(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    username = request.POST.get("creator_username") or ""
    username = username.strip()
    if not username:
        return JsonResponse({"ok": False, "reason": "invalid_creator"}, status=400)

    creator = User.objects.filter(username=username).select_related("profile").first()
    if not creator:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    if creator.id == request.user.id:
        return JsonResponse({"ok": False, "reason": "cannot_follow_self"}, status=400)

    # مطمئن باش profile هست
    UserProfile.objects.get_or_create(user=creator)

    following = False
    try:
        with transaction.atomic():
            CreatorFollow.objects.create(user=request.user, creator=creator)
            UserProfile.objects.filter(user=creator).update(follower_count=F("follower_count") + 1)
            following = True
    except IntegrityError:
        with transaction.atomic():
            CreatorFollow.objects.filter(user=request.user, creator=creator).delete()
            UserProfile.objects.filter(user=creator, follower_count__gt=0).update(follower_count=F("follower_count") - 1)
            following = False

    creator.profile.refresh_from_db(fields=["follower_count"])
    return JsonResponse({"ok": True, "following": following, "follower_count": creator.profile.follower_count})


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@require_POST
def comment_add(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    if not track_id or not str(track_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    track = Track.objects.filter(id=int(track_id)).select_related("creator").first()
    if not track:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    result = services.add_comment(author=request.user, track=track, body=request.POST.get("body", ""))
    if not result.ok:
        status = 404 if result.reason == "not_found" else 400
        return JsonResponse({"ok": False, "reason": result.reason}, status=status)

    c = result.comment
    return JsonResponse({
        "ok": True,
        "comment": {
            "id": c.id,
            "body": c.body,
            "author_username": c.author.username,
            "created_at": c.created_at.isoformat(),
        },
    })


@require_POST
def comment_delete(request, comment_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    comment = get_object_or_404(Comment, id=comment_id)
    result = services.delete_comment(user=request.user, comment=comment)
    if not result.ok:
        return JsonResponse({"ok": False, "reason": result.reason}, status=403)
    return JsonResponse({"ok": True})


@require_POST
def comment_like(request, comment_id: int):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    comment = get_object_or_404(Comment, id=comment_id)
    result = services.toggle_comment_like(user=request.user, comment=comment)
    if not result.ok:
        return JsonResponse({"ok": False, "reason": result.reason}, status=404)
    return JsonResponse({"ok": True, "liked": result.active, "like_count": result.count})


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

@require_POST
def toggle_favorite(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    if not track_id or not str(track_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    track = Track.objects.filter(id=int(track_id)).first()
    if not track:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    result = services.toggle_favorite(user=request.user, track=track)
    if not result.ok:
        return JsonResponse({"ok": False, "reason": result.reason}, status=404)
    return JsonResponse({"ok": True, "favorited": result.active, "favorite_count": result.count})


# ---------------------------------------------------------------------------
# Repost
# ---------------------------------------------------------------------------

@require_POST
def toggle_repost(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    if not track_id or not str(track_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    track = Track.objects.filter(id=int(track_id)).first()
    if not track:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    result = services.toggle_repost(user=request.user, track=track)
    if not result.ok:
        status = 404 if result.reason == "not_found" else 400
        return JsonResponse({"ok": False, "reason": result.reason}, status=status)
    return JsonResponse({"ok": True, "reposted": result.active, "repost_count": result.count})


# ---------------------------------------------------------------------------
# Creator block (mute a commenter from your own tracks)
# ---------------------------------------------------------------------------

@require_POST
def toggle_block(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    username = (request.POST.get("blocked_username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "reason": "invalid_user"}, status=400)

    target = User.objects.filter(username=username).first()
    if not target:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    result = services.toggle_creator_block(creator=request.user, blocked_user=target)
    if not result.ok:
        return JsonResponse({"ok": False, "reason": result.reason}, status=400)
    return JsonResponse({"ok": True, "blocked": result.active})
