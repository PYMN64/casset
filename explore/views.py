from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
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

    # Lightweight, explainable recommendations (S12) — genre affinity +
    # popularity + freshness, computed and cached in the service layer.
    # See explore/services.py::get_personalized_recommendations for the
    # scoring model and its own fallback for users with no play history.
    recommended = services.get_personalized_recommendations(
        request.user, content_type=selected_type, limit=6,
    )

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
    """Server-rendered results.

    The page used to render nothing at all server-side and rely entirely on
    a JS fetch, which meant no result was ever in the HTML — bad for a
    slow connection and invisible to anything without JavaScript. The live
    JS layer still enhances it; this is the floor beneath it.
    """
    setting = PlatformSetting.get_solo()
    enabled_types = [
        t for t in ["music", "podcast", "book", "video"]
        if setting.is_content_type_enabled(t)
    ]
    selected_type = (request.GET.get("type") or "all").lower()
    if selected_type not in ["all"] + enabled_types:
        selected_type = "all"

    query = (request.GET.get("q") or "").strip()
    tracks, creators = [], []
    if query:
        tracks = list(services.search_track_queryset(query, content_type=selected_type))
        creators = list(
            User.objects.filter(
                profile__public_handle__isnull=False, is_active=True,
            ).filter(
                Q(profile__display_name__icontains=query)
                | Q(profile__public_handle__icontains=query)
            ).select_related("profile")[:8]
        )

    return render(request, "explore/search.html", {
        "query": query,
        "tracks": tracks,
        "creators": creators,
        "enabled_types": enabled_types,
        "selected_type": selected_type,
        "nav_active": "search",
    })


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

@require_GET
def api_station(request, username):
    creator = User.objects.filter(username=username).first()
    if not creator:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    exclude_id = request.GET.get("exclude")
    exclude_id = int(exclude_id) if exclude_id and exclude_id.isdigit() else None

    tracks = services.station_for_creator(creator, exclude_track_id=exclude_id)
    items = [
        {
            "src": t.audio.url,
            "title": t.title,
            "by": f"@{t.creator.username}",
            "cover": t.cover.url if t.cover else "",
            "trackId": t.id,
            "peaks": t.waveform_peaks or [],
        }
        for t in tracks
    ]
    return JsonResponse({"ok": True, "items": items})


def trending_view(request):
    since = (date.today() - timedelta(days=7)).isoformat()
    setting = PlatformSetting.get_solo()

    # Content-type filter, matching discover_view. This page previously had
    # none at all, so a podcast listener had to scroll past every song to
    # find the chart that applied to them.
    enabled_types = [
        t for t in ["music", "podcast", "book", "video"]
        if setting.is_content_type_enabled(t)
    ]
    selected_type = (request.GET.get("type") or "all").lower()
    if selected_type not in ["all"] + enabled_types:
        selected_type = "all"

    # Same qualified-plays basis as discover_view — see the comment there.
    trending_ids = (
        PlayEvent.objects.filter(day_key__gte=since, point_awarded=True)
        .values("track_id")
        .annotate(c=Count("id"))
        .order_by("-c")[:50]
    )
    trending_map = {row["track_id"]: row["c"] for row in trending_ids}

    tracks_qs = (
        Track.objects.filter(
            id__in=list(trending_map.keys()),
            status=Track.Status.APPROVED,
            visibility=Track.Visibility.PUBLIC,
        )
        .select_related("creator", "creator__profile")
        .prefetch_related("genres")
    )
    if selected_type == "book":
        tracks_qs = tracks_qs.filter(content_type__in=["book", "audiobook"])
    elif selected_type != "all":
        tracks_qs = tracks_qs.filter(content_type=selected_type)

    trending_tracks = sorted(tracks_qs, key=lambda t: trending_map.get(t.id, 0), reverse=True)

    return render(request, "explore/trending.html", {
        # `tracks` is the name the template (and _track_row.html) uses;
        # `trending_tracks` is kept for any caller that still expects it.
        "tracks": trending_tracks,
        "trending_tracks": trending_tracks,
        "enabled_types": enabled_types,
        "selected_type": selected_type,
        "nav_active": "trending",
    })
