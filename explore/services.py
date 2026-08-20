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
