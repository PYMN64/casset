from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from tracks.models import Track
from .models import CreatorFollow, TrackLike

User = get_user_model()


def _rate_limited(key: str, limit: int = 30, window: int = 10) -> bool:
    try:
        from django.core.cache import cache
    except Exception:
        return False

    cur = cache.get(key, 0)
    if cur >= limit:
        return True
    cache.set(key, cur + 1, timeout=window)
    return False


@require_POST
def toggle_like(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "reason": "auth_required"}, status=401)

    if _rate_limited(f"rl:like:{request.user.id}"):
        return JsonResponse({"ok": False, "reason": "rate_limited"}, status=429)

    track_id = request.POST.get("track_id")
    if not track_id or not str(track_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    track = Track.objects.filter(
        id=int(track_id),
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    ).first()
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

    if _rate_limited(f"rl:follow:{request.user.id}"):
        return JsonResponse({"ok": False, "reason": "rate_limited"}, status=429)

    username = (request.POST.get("creator_username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "reason": "invalid_creator"}, status=400)

    creator = User.objects.filter(username=username).select_related("profile").first()
    if not creator:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    if creator.id == request.user.id:
        return JsonResponse({"ok": False, "reason": "cannot_follow_self"}, status=400)

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
            UserProfile.objects.filter(user=creator, follower_count__gt=0).update(
                follower_count=F("follower_count") - 1
            )
            following = False

    creator.profile.refresh_from_db(fields=["follower_count"])
    return JsonResponse({"ok": True, "following": following, "follower_count": creator.profile.follower_count})
