"""explore/services.py — search.

Branches on the DB backend rather than adding a persisted SearchVectorField
+ GIN index: dev/test run on SQLite by default (pyproject.toml's default
DJANGO_SETTINGS_MODULE=config.settings.dev), and a migration that adds a
Postgres-only field type would break `makemigrations`/`migrate` there.
Annotating SearchVector at query time costs more per-query than a stored
column would at real scale, but is correct on both backends with zero
migration risk — the right tradeoff until traffic actually demands the
stored+indexed version.
"""

from collections import Counter
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone as dj_timezone

from plays.models import PlayEvent
from tracks.models import Genre, Track

User = get_user_model()

_MAX_RESULTS = 10


def search_track_queryset(query: str, *, content_type: str = "all", limit: int = 40):
    """Full-text search returning real Track objects.

    Separate from `search_tracks` on purpose: that one returns `.values()`
    dicts shaped for the JSON autocomplete API and must keep doing so,
    while the search *page* renders the same card partials as the rest of
    the site and therefore needs model instances.

    Same Postgres/SQLite branch as the rest of this module — see the module
    docstring for why the backend check lives at query time.
    """
    base = Track.objects.filter(
        status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
    ).select_related("creator", "creator__profile")

    if content_type == "book":
        base = base.filter(content_type__in=["book", "audiobook"])
    elif content_type and content_type != "all":
        base = base.filter(content_type=content_type)

    if not query:
        return base.none()

    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = SearchVector("title", weight="A") + SearchVector("description", weight="B")
        search_query = SearchQuery(query)
        return (
            base.annotate(rank=SearchRank(vector, search_query))
            .filter(rank__gt=0)
            .order_by("-rank", "-play_count")[:limit]
        )

    from django.db.models import Q

    return (
        base.filter(Q(title__icontains=query) | Q(description__icontains=query))
        .order_by("-play_count")[:limit]
    )


def search_tracks(query: str):
    base = Track.objects.filter(
        status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
    ).select_related("creator")

    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = SearchVector("title", weight="A") + SearchVector("description", weight="B")
        search_query = SearchQuery(query)
        return list(
            base.annotate(rank=SearchRank(vector, search_query))
            .filter(rank__gt=0)
            .order_by("-rank", "-play_count")[:_MAX_RESULTS]
            .values("id", "title", "slug", "play_count", "creator__username")
        )

    return list(
        base.filter(title__icontains=query)
        .order_by("-play_count")[:_MAX_RESULTS]
        .values("id", "title", "slug", "play_count", "creator__username")
    )


def search_creators(query: str):
    base = User.objects.select_related("profile")

    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = SearchVector("username", weight="A") + SearchVector("profile__display_name", weight="B")
        search_query = SearchQuery(query)
        return list(
            base.annotate(rank=SearchRank(vector, search_query))
            .filter(rank__gt=0)
            .order_by("-rank", "username")[:_MAX_RESULTS]
            .values("username", "profile__follower_count")
        )

    return list(
        base.filter(username__icontains=query)
        .order_by("username")[:_MAX_RESULTS]
        .values("username", "profile__follower_count")
    )


def search_genres(query: str):
    return list(
        Genre.objects.filter(name__icontains=query)
        .order_by("name")[:_MAX_RESULTS]
        .values("name", "slug")
    )


_STATION_SIZE = 25


def station_for_creator(creator, *, exclude_track_id=None):
    """'Radio' queue for continuous play: a creator's other public tracks,
    randomly ordered so replaying the station doesn't always start the same
    way. Keeps the query scoped to one creator rather than mixing in
    similar-genre tracks from others — a simpler, correctly-scoped v1 that
    a genre-aware version can later extend without changing the call site.
    """
    qs = Track.objects.filter(
        creator=creator, status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
    ).exclude(audio="").select_related("creator")
    if exclude_track_id:
        qs = qs.exclude(id=exclude_track_id)
    return list(qs.order_by("?")[:_STATION_SIZE])


# ---------------------------------------------------------------------------
# Lightweight Discover recommendations (S12)
#
# Deliberately NOT a trained/ML model (see CLAUDE.md phase-2 plan §4.3 —
# "یک لایه‌ی توصیهٔ سبک ... نه AI مولد"): a small, fully explainable
# weighted score over three signals —
#   1. genre affinity  — how often this listener has played this track's
#      genre(s) before (from PlayEvent, the same raw source discover_view
#      already used for its old inline version of this).
#   2. popularity       — track.play_count, normalised against the
#      candidate pool so it never swamps the other two signals.
#   3. freshness        — exponential decay by days since publish, so a new
#      upload from a genre the listener likes can still surface.
# Falls back to a popularity+recency list (no genre signal at all) for
# anonymous visitors and listeners with no play history yet.
# ---------------------------------------------------------------------------

_RECS_CACHE_TTL_SECONDS = 20 * 60
_RECS_CANDIDATE_POOL = 100
_RECS_DEFAULT_LIMIT = 6
_RECS_GENRE_HISTORY_CAP = 2000  # bound the raw PlayEvent scan for very active listeners

_RECS_GENRE_WEIGHT = 3.0
_RECS_POPULARITY_WEIGHT = 1.0
_RECS_FRESHNESS_WEIGHT = 1.5
_RECS_FRESHNESS_HALF_LIFE_DAYS = 14


def _apply_recs_content_type(qs, content_type: str):
    """Same content-type mapping discover_view/search use — kept local
    here (not shared) since each call site already has its own copy;
    unifying them is a separate refactor, out of scope for S12."""
    if content_type == "book":
        return qs.filter(content_type__in=["book", "audiobook"])
    if content_type and content_type != "all":
        return qs.filter(content_type=content_type)
    return qs


def _popular_recent_fallback(base_qs, limit: int) -> list:
    """No usable genre signal (new/anonymous listener) — surface what a
    platform-agnostic 'reason to come back' page shows by default: recently
    published content, ranked by how well it's already doing. Tops up with
    all-time popular tracks if recent publishing volume is too thin to fill
    `limit` on its own (expected on a young/quiet platform)."""
    recent_cutoff = dj_timezone.now() - timedelta(days=90)
    recent_popular = list(
        base_qs.filter(published_at__gte=recent_cutoff).order_by("-play_count")[:limit]
    )
    if len(recent_popular) >= limit:
        return recent_popular
    seen_ids = {t.id for t in recent_popular}
    topup = list(
        base_qs.exclude(id__in=seen_ids).order_by("-play_count")[: limit - len(recent_popular)]
    )
    return recent_popular + topup


def get_personalized_recommendations(user, *, content_type: str = "all", limit: int = _RECS_DEFAULT_LIMIT) -> list:
    """Discover's 'پیشنهاد برای تو' section. See module comment above for
    the scoring model. Cached per (user, content_type, limit) for
    _RECS_CACHE_TTL_SECONDS so this never re-scans PlayEvent history on
    every Discover page load.
    """
    from django.core.cache import cache

    user_id = getattr(user, "id", None) if user is not None else None
    is_authenticated = bool(getattr(user, "is_authenticated", False))
    cache_key = f"explore:recs:{user_id if is_authenticated else 'anon'}:{content_type}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base_qs = _apply_recs_content_type(
        Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        .select_related("creator")
        .prefetch_related("genres"),
        content_type,
    )

    genre_weights: dict = {}
    played_track_ids: set = set()
    if is_authenticated:
        history = PlayEvent.objects.filter(user=user).exclude(track__genres=None)
        genre_ids = history.values_list("track__genres__id", flat=True)[:_RECS_GENRE_HISTORY_CAP]
        genre_weights = dict(Counter(genre_ids))
        played_track_ids = set(
            PlayEvent.objects.filter(user=user).values_list("track_id", flat=True)[:_RECS_GENRE_HISTORY_CAP]
        )

    if not genre_weights:
        result = _popular_recent_fallback(base_qs, limit)
        cache.set(cache_key, result, _RECS_CACHE_TTL_SECONDS)
        return result

    candidates = list(
        base_qs.filter(genres__id__in=genre_weights.keys())
        .exclude(id__in=played_track_ids)
        .distinct()[:_RECS_CANDIDATE_POOL]
    )
    if not candidates:
        result = _popular_recent_fallback(base_qs, limit)
        cache.set(cache_key, result, _RECS_CACHE_TTL_SECONDS)
        return result

    now = dj_timezone.now()
    max_play_count = max((t.play_count for t in candidates), default=0) or 1
    max_genre_weight = max(genre_weights.values(), default=1) or 1

    def _score(track) -> float:
        genre_score = max((genre_weights.get(g.id, 0) for g in track.genres.all()), default=0)
        popularity_score = track.play_count / max_play_count
        published = track.published_at or track.created_at
        age_days = max((now - published).total_seconds() / 86400.0, 0.0) if published else 999.0
        freshness_score = 0.5 ** (age_days / _RECS_FRESHNESS_HALF_LIFE_DAYS)
        return (
            _RECS_GENRE_WEIGHT * (genre_score / max_genre_weight)
            + _RECS_POPULARITY_WEIGHT * popularity_score
            + _RECS_FRESHNESS_WEIGHT * freshness_score
        )

    ranked = sorted(candidates, key=_score, reverse=True)[:limit]
    cache.set(cache_key, ranked, _RECS_CACHE_TTL_SECONDS)
    return ranked
