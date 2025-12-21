from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import PlatformSetting
from plays.models import PlayEvent
from tracks.models import Genre, Track
from .models import FeaturedPin

User = get_user_model()


def _rate_limited(request) -> bool:
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
    book_types = ["book", "audiobook"]

    enabled_types = [
        t for t in ["music", "podcast", "book", "video"] if setting.is_content_type_enabled(t)
    ]
    if selected_type not in ["all"] + enabled_types:
        selected_type = "all"

    def apply_type(qs):
        if selected_type == "all":
            return qs.filter(content_type__in=["music", "podcast"] + book_types + ["video"])
        if selected_type == "book":
            return qs.filter(content_type__in=book_types)
        return qs.filter(content_type=selected_type)

    since = (date.today() - timedelta(days=7)).isoformat()

    trending_ids = (
        PlayEvent.objects.filter(day_key__gte=since)
        .values("track_id")
        .annotate(c=Count("id"))
        .order_by("-c")[:20]
    )
    trending_map = {row["track_id"]: row["c"] for row in trending_ids}
    trending_tracks = (
        apply_type(
            Track.objects.filter(
                id__in=list(trending_map.keys()),
                status=Track.Status.APPROVED,
                visibility=Track.Visibility.PUBLIC,
            )
        )
        .select_related("creator")
        .prefetch_related("genres")
    )
    trending_tracks = sorted(trending_tracks, key=lambda t: trending_map.get(t.id, 0), reverse=True)

    new_tracks = (
        apply_type(
            Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        )
        .select_related("creator")
        .prefetch_related("genres")
        .order_by("-created_at")[:20]
    )

    most_viewed = (
        apply_type(
            Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        )
        .select_related("creator")
        .prefetch_related("genres")
        .order_by("-play_count")[:12]
    )

    now = timezone.now()
    pins_qs = (
        FeaturedPin.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
    )
    pinned = []
    for pin in pins_qs.select_related("track", "track__creator"):
        track = pin.track
        if not track:
            continue
        if track.status != Track.Status.APPROVED or track.visibility != Track.Visibility.PUBLIC:
            continue
        if selected_type != "all":
            if selected_type == "book" and track.content_type not in book_types:
                continue
            if selected_type != "book" and track.content_type != selected_type:
                continue
        pinned.append(pin)

    if request.user.is_authenticated:
        recent_genres = (
            Genre.objects.filter(is_active=True, tracks__play_events__user=request.user)
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

    genres = Genre.objects.filter(is_active=True).order_by("content_type", "order", "name_fa")[:60]

    return render(
        request,
        "explore/discover.html",
        {
            "enabled_types": enabled_types,
            "selected_type": selected_type,
            "pinned": pinned,
            "trending_tracks": trending_tracks,
            "new_tracks": new_tracks,
            "most_viewed": most_viewed,
            "recommended": recommended,
            "genres": genres,
        },
    )


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

    tracks = (
        Track.objects.filter(
            status=Track.Status.APPROVED,
            visibility=Track.Visibility.PUBLIC,
            title__icontains=q2,
        )
        .select_related("creator")
        .order_by("-play_count")[:10]
        .values("id", "title", "slug", "play_count", "creator__username")
    )

    creators = (
        User.objects.filter(username__icontains=q2)
        .select_related("profile")
        .order_by("username")[:10]
        .values("username", "profile__follower_count")
    )

    genres_qs = (
        Genre.objects.filter(Q(name_fa__icontains=q2) | Q(name_en__icontains=q2), is_active=True)
        .order_by("content_type", "order", "name_fa")[:10]
    )
    genres = [{"name": g.name, "slug": g.slug} for g in genres_qs]

    return JsonResponse(
        {
            "ok": True,
            "q": q,
            "tracks": list(tracks),
            "creators": list(creators),
            "genres": genres,
        }
    )


def trending_view(request):
    since = (date.today() - timedelta(days=7)).isoformat()

    trending_ids = (
        PlayEvent.objects.filter(day_key__gte=since)
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
        .select_related("creator")
        .prefetch_related("genres")
    )
    trending_tracks = sorted(tracks_qs, key=lambda t: trending_map.get(t.id, 0), reverse=True)

    return render(request, "explore/trending.html", {"trending_tracks": trending_tracks})
