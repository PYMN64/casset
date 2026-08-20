from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.models import PlatformSetting
from interactions.models import CreatorFollow
from plays.models import PlayEvent
from tracks.models import Genre, Track

from . import services
from .models import FeaturedPin

User = get_user_model()


def _rate_limited(request) -> bool:
    # خیلی سبک: هر IP در 10 ثانیه حداکثر 20 سرچ
    try:
        from django.core.cache import cache
    except Exception:
        return False

    ip = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    key = f"rl:search:{ip}"
    cur = cache.get(key, 0)
    if cur >= 20:
        return True
    cache.set(key, cur + 1, timeout=10)
    return False


def discover_view(request):
    recommended = []
    setting = PlatformSetting.get_solo()
    selected_type = (request.GET.get("type") or "all").lower()

    # Only show enabled content types (admin-controlled)
    enabled_types = [
        t for t in ["music", "podcast", "book", "video"]
        if setting.is_content_type_enabled(t)
    ]
    if selected_type not in ["all"] + enabled_types:
        selected_type = "all"

    def apply_type(qs):
        if selected_type == "all":
            return qs.filter(content_type__in=["music", "podcast", "audiobook", "video"])
        if selected_type == "book":
            return qs.filter(content_type__in=["book", "audiobook"])
        return qs.filter(content_type=selected_type)

    # Trending = qualified plays only (PlayEvent.point_awarded=True), not raw
    # PlayEvent rows. Raw events include everything a listener's browser
    # registered, whether or not it passed the fraud/time gates in
    # plays/services.py — trending should reflect real engagement, the same
    # bar creators are actually paid against.
    since = (date.today() - timedelta(days=7)).isoformat()

    trending_ids = (
        PlayEvent.objects.filter(day_key__gte=since, point_awarded=True)
        .values("track_id")
        .annotate(c=Count("id"))
        .order_by("-c")[:20]
    )
    trending_map = {row["track_id"]: row["c"] for row in trending_ids}
    trending_tracks = (
        apply_type(Track.objects.filter(id__in=list(trending_map.keys()), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC))
        .select_related("creator")
        .prefetch_related("genres")
    )
    # حفظ ترتیب بر اساس شمارش
    trending_tracks = sorted(trending_tracks, key=lambda t: trending_map.get(t.id, 0), reverse=True)

    new_tracks = (
        apply_type(Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC))
        .select_related("creator")
        .prefetch_related("genres")
        .order_by("-created_at")[:20]
    )

    most_viewed = (
        apply_type(Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC))
        .select_related("creator")
        .prefetch_related("genres")
        .order_by("-play_count")[:12]
    )

    # Admin-controlled pins
    pins_qs = FeaturedPin.objects.filter(is_active=True)
    pinned = []
    for pin in pins_qs.select_related("track", "track__creator"):
        if pin.track and pin.track.status == Track.Status.APPROVED:
            if selected_type != "all":
                if selected_type == "book" and pin.track.content_type not in ["book", "audiobook"]:
                    continue
                if selected_type not in ["book"] and pin.track.content_type != selected_type:
                    continue
            pinned.append(pin)

    # Personalized feed: latest tracks from creators the user follows. This
    # is the "reason to come back" the product strategy calls for — shown
    # above trending/pinned in the template when non-empty. Empty for
    # anonymous users and users who don't follow anyone yet (falls back to
    # the general sections below, nothing else to show them here).
    followed_feed = []
    if request.user.is_authenticated:
        followed_ids = CreatorFollow.objects.filter(user=request.user).values_list("creator_id", flat=True)
        if followed_ids:
            followed_feed = list(
                apply_type(
                    Track.objects.filter(
                        creator_id__in=list(followed_ids),
                        status=Track.Status.APPROVED,
                        visibility=Track.Visibility.PUBLIC,
                    )
                )
                .select_related("creator")
                .prefetch_related("genres")
                .order_by("-published_at", "-created_at")[:20]
            )

    # Lightweight recommendations: last played genres or fallback to trending.
    # (Regression fix: this block used to sit accidentally nested inside the
    # `for pin in pins_qs` loop above, so it only ran when there was at least
    # one active FeaturedPin — completely unrelated to why it should run.)
    recommended = []
    if request.user.is_authenticated:
        recent_genres = (
            Genre.objects.filter(tracks__play_events__user=request.user)
            .distinct()
            .annotate(c=Count("id"))
            .order_by("-c")[:3]
        )
        if recent_genres:
            recommended = (
                apply_type(
                    Track.objects.filter(
                        status=Track.Status.APPROVED,
                        visibility=Track.Visibility.PUBLIC,
                        genres__in=list(recent_genres),
                    )
                )
                .select_related("creator")
                .prefetch_related("genres")
                .distinct()
                .order_by("-play_count")[:6]
            )

    if not recommended:
        recommended = trending_tracks[:6]

    # Suggested creators — the other half of the "reason to come back" loop:
    # followed_feed only has content once you follow someone, so new/quiet
    # users need a low-friction way to find their first few follows. Ranked
    # by follower_count as a simple, no-ML popularity signal (same rationale
    # as `recommended` above), restricted to accounts that have actually
    # published something public — no point suggesting an empty profile.
    suggested_creators_qs = (
        User.objects.filter(
            tracks__status=Track.Status.APPROVED,
            tracks__visibility=Track.Visibility.PUBLIC,
        )
        .exclude(id=getattr(request.user, "id", None))
        .select_related("profile")
        .distinct()
        .order_by("-profile__follower_count")
    )
    if request.user.is_authenticated:
        already_followed = CreatorFollow.objects.filter(user=request.user).values_list("creator_id", flat=True)
        suggested_creators_qs = suggested_creators_qs.exclude(id__in=list(already_followed))
    suggested_creators = list(suggested_creators_qs[:6])

    genres = Genre.objects.all().order_by("name")[:60]

    return render(request, "explore/discover.html", {
        "enabled_types": enabled_types,
        "selected_type": selected_type,
        "pinned": pinned,
        "followed_feed": followed_feed,
        "trending_tracks": trending_tracks,
        "new_tracks": new_tracks,
        "most_viewed": most_viewed,
        "recommended": recommended,
        "suggested_creators": suggested_creators,
        "genres": genres,
    })


def search_view(request):
    return render(request, "explore/search.html")


@require_GET
def api_search(request):
    if _rate_limited(request):
        return JsonResponse({"ok": False, "reason": "rate_limited"}, status=429)

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": True, "q": q, "tracks": [], "creators": [], "genres": []})

    q2 = q[:60]

    return JsonResponse({
        "ok": True,
        "q": q,
        "tracks": services.search_tracks(q2),
        "creators": services.search_creators(q2),
        "genres": services.search_genres(q2),
    })

def trending_view(request):
    since = (date.today() - timedelta(days=7)).isoformat()

    # Same qualified-plays basis as discover_view — see the comment there.
    trending_ids = (
        PlayEvent.objects.filter(day_key__gte=since, point_awarded=True)
        .values("track_id")
        .annotate(c=Count("id"))
        .order_by("-c")[:50]
    )
    trending_map = {row["track_id"]: row["c"] for row in trending_ids}

    tracks_qs = (
        Track.objects.filter(id__in=list(trending_map.keys()), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        .select_related("creator")
        .prefetch_related("genres")
    )
    trending_tracks = sorted(tracks_qs, key=lambda t: trending_map.get(t.id, 0), reverse=True)

    return render(request, "explore/trending.html", {"trending_tracks": trending_tracks})
