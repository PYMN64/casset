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

from django.contrib.auth import get_user_model
from django.db import connection

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
