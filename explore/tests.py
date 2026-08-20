"""explore/tests.py — Tests for the Discover page (Phase 4/5: personalized
feed, qualified-play-weighted trending, and creator suggestions).

This view had zero test coverage before this session despite carrying the
platform's single most important retention mechanic (the "reason to come
back" personalized feed) — these tests lock that behavior in.
"""

from datetime import date, timedelta
from unittest import skipUnless

from django.db import connection
from django.test import TestCase
from django.urls import reverse

from core.test_utils import make_user
from interactions.models import CreatorFollow
from plays.models import PlayEvent
from tracks.models import Genre, Track

from . import services
from .models import FeaturedPin


def make_track(creator, **extra):
    defaults = dict(
        title="T",
        content_type=Track.ContentType.MUSIC,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    )
    defaults.update(extra)
    return Track.objects.create(creator=creator, **defaults)


def make_play_event(track, *, ip_hash="ip1", day_key=None, point_awarded=False, user=None):
    return PlayEvent.objects.create(
        track=track,
        user=user,
        ip_hash=ip_hash,
        ua_hash="ua1",
        day_key=day_key or date.today().isoformat(),
        point_awarded=point_awarded,
    )


class FollowedFeedTests(TestCase):
    def setUp(self):
        self.viewer = make_user("ff_viewer")
        self.followed = make_user("ff_followed")
        self.stranger = make_user("ff_stranger")
        self.followed_track = make_track(self.followed, title="Followed track")
        self.stranger_track = make_track(self.stranger, title="Stranger track")
        CreatorFollow.objects.create(user=self.viewer, creator=self.followed)

    def test_anonymous_sees_no_followed_feed(self):
        resp = self.client.get(reverse("discover"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["followed_feed"]), [])

    def test_logged_in_sees_only_followed_creators_tracks(self):
        self.client.login(username="ff_viewer", password="pass12345")
        resp = self.client.get(reverse("discover"))
        feed = list(resp.context["followed_feed"])
        self.assertIn(self.followed_track, feed)
        self.assertNotIn(self.stranger_track, feed)

    def test_user_who_follows_nobody_gets_empty_feed(self):
        make_user("ff_lonely")
        self.client.login(username="ff_lonely", password="pass12345")
        resp = self.client.get(reverse("discover"))
        self.assertEqual(list(resp.context["followed_feed"]), [])

    def test_unapproved_track_from_followed_creator_excluded(self):
        make_track(self.followed, title="Draft", status=Track.Status.DRAFT)
        self.client.login(username="ff_viewer", password="pass12345")
        resp = self.client.get(reverse("discover"))
        titles = {t.title for t in resp.context["followed_feed"]}
        self.assertNotIn("Draft", titles)

    def test_private_track_from_followed_creator_excluded(self):
        make_track(self.followed, title="Private", visibility=Track.Visibility.PRIVATE)
        self.client.login(username="ff_viewer", password="pass12345")
        resp = self.client.get(reverse("discover"))
        titles = {t.title for t in resp.context["followed_feed"]}
        self.assertNotIn("Private", titles)


class TrendingWeightingTests(TestCase):
    """Trending must reflect Qualified Plays (point_awarded=True), not every
    raw PlayEvent a browser reported — otherwise a bot/fast-skip flood that
    never passed the fraud gates in plays/services.py could still dominate
    the platform's most visible discovery surface."""

    def setUp(self):
        self.creator = make_user("tw_creator")
        self.qualified_track = make_track(self.creator, title="Qualified")
        self.unqualified_track = make_track(self.creator, title="Unqualified")

    def test_only_qualified_plays_count_toward_trending(self):
        for i in range(5):
            make_play_event(self.qualified_track, ip_hash=f"q{i}", point_awarded=True)
        for i in range(20):
            make_play_event(self.unqualified_track, ip_hash=f"u{i}", point_awarded=False)

        resp = self.client.get(reverse("discover"))
        trending = list(resp.context["trending_tracks"])
        self.assertIn(self.qualified_track, trending)
        self.assertNotIn(self.unqualified_track, trending)

    def test_trending_page_uses_same_qualified_basis(self):
        make_play_event(self.qualified_track, ip_hash="q1", point_awarded=True)
        make_play_event(self.unqualified_track, ip_hash="u1", point_awarded=False)

        resp = self.client.get(reverse("trending"))
        trending = list(resp.context["trending_tracks"])
        self.assertIn(self.qualified_track, trending)
        self.assertNotIn(self.unqualified_track, trending)

    def test_stale_plays_outside_the_7_day_window_dont_count(self):
        old_day = (date.today() - timedelta(days=30)).isoformat()
        make_play_event(self.qualified_track, ip_hash="old", day_key=old_day, point_awarded=True)

        resp = self.client.get(reverse("discover"))
        self.assertNotIn(self.qualified_track, list(resp.context["trending_tracks"]))


class SuggestedCreatorsTests(TestCase):
    def setUp(self):
        self.viewer = make_user("sc_viewer")
        self.publisher = make_user("sc_publisher")
        make_track(self.publisher, title="Public track")

    def test_publisher_with_public_track_is_suggested(self):
        resp = self.client.get(reverse("discover"))
        suggested = list(resp.context["suggested_creators"])
        self.assertIn(self.publisher, suggested)

    def test_user_without_any_public_track_is_not_suggested(self):
        make_user("sc_lurker")
        resp = self.client.get(reverse("discover"))
        usernames = {u.username for u in resp.context["suggested_creators"]}
        self.assertNotIn("sc_lurker", usernames)

    def test_self_never_suggested(self):
        self.client.login(username="sc_publisher", password="pass12345")
        resp = self.client.get(reverse("discover"))
        self.assertNotIn(self.publisher, list(resp.context["suggested_creators"]))

    def test_already_followed_creator_not_suggested_again(self):
        CreatorFollow.objects.create(user=self.viewer, creator=self.publisher)
        self.client.login(username="sc_viewer", password="pass12345")
        resp = self.client.get(reverse("discover"))
        self.assertNotIn(self.publisher, list(resp.context["suggested_creators"]))

    def test_anonymous_still_gets_suggestions(self):
        resp = self.client.get(reverse("discover"))
        self.assertGreaterEqual(len(list(resp.context["suggested_creators"])), 1)


class PinnedAndTypeFilterTests(TestCase):
    def setUp(self):
        self.creator = make_user("pf_creator")
        self.track = make_track(self.creator, title="Pinned")

    def test_inactive_pin_not_shown(self):
        FeaturedPin.objects.create(track=self.track, is_active=False)
        resp = self.client.get(reverse("discover"))
        self.assertEqual(len(resp.context["pinned"]), 0)

    def test_active_pin_shown(self):
        FeaturedPin.objects.create(track=self.track, is_active=True)
        resp = self.client.get(reverse("discover"))
        self.assertEqual(len(resp.context["pinned"]), 1)

    def test_invalid_type_falls_back_to_all(self):
        resp = self.client.get(reverse("discover") + "?type=not_a_real_type")
        self.assertEqual(resp.context["selected_type"], "all")


# ---------------------------------------------------------------------------
# Search (explore/services.py) — the SQLite path is what CI/dev actually
# exercises (pyproject.toml's default settings module runs sqlite); the
# PostgreSQL SearchVector/SearchRank path is skipped here and instead
# verified against a real Postgres server (see .casset/state/changelog.md).
# ---------------------------------------------------------------------------

class SearchTracksTests(TestCase):
    def setUp(self):
        self.creator = make_user("search_creator")
        self.match = make_track(self.creator, title="Shabaviz Live")
        self.other = make_track(self.creator, title="Unrelated Track")
        make_track(self.creator, title="Hidden Draft", status=Track.Status.DRAFT)

    def test_matches_title_case_insensitively(self):
        results = services.search_tracks("shabaviz")
        ids = [r["id"] for r in results]
        self.assertIn(self.match.id, ids)
        self.assertNotIn(self.other.id, ids)

    def test_excludes_non_public_or_unapproved_tracks(self):
        results = services.search_tracks("Hidden")
        self.assertEqual(results, [])

    def test_orders_by_play_count(self):
        Track.objects.filter(pk=self.other.pk).update(title="Shabaviz Extra", play_count=100)
        results = services.search_tracks("shabaviz")
        self.assertEqual(results[0]["id"], self.other.pk)


class SearchCreatorsTests(TestCase):
    def test_matches_username(self):
        make_user("findable_creator_x")
        results = services.search_creators("findable_creator")
        usernames = [r["username"] for r in results]
        self.assertIn("findable_creator_x", usernames)

    def test_no_match_returns_empty(self):
        self.assertEqual(services.search_creators("zzz_no_such_user"), [])


class SearchGenresTests(TestCase):
    def test_matches_genre_name(self):
        Genre.objects.create(name="Traditional Persian", slug="traditional-persian")
        results = services.search_genres("Persian")
        self.assertEqual(len(results), 1)


@skipUnless(connection.vendor == "postgresql", "SearchVector/SearchRank only runs on PostgreSQL")
class SearchFullTextPostgresTests(TestCase):
    """Only executes when the test suite is run against a real Postgres
    server (see .casset/state/changelog.md for the pgserver-based
    verification runs used in prior phases) — SQLite is the default and
    can't exercise this branch."""

    def setUp(self):
        self.creator = make_user("pg_search_creator")
        self.by_title = make_track(self.creator, title="Zarathustra Podcast")
        self.by_description = make_track(
            self.creator, title="Unrelated", description="A show about Zarathustra history",
        )

    def test_ranks_title_match_above_description_match(self):
        results = services.search_tracks("Zarathustra")
        ids = [r["id"] for r in results]
        self.assertEqual(ids[0], self.by_title.id)
        self.assertIn(self.by_description.id, ids)
