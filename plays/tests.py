"""plays/tests.py — Tests for play registration and point award system."""

from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from accounts.models import UserProfile
from core.test_utils import make_user
from tracks.models import Track

from .geo import resolve_country_code, resolve_device_type
from .models import DailyTrackStat, FraudFlag, PlaybackSession, PlayEvent, PointLedger
from .services import (
    aggregate_daily_stats,
    get_creator_geo_device_breakdown,
    get_creator_stats_series,
    start_playback_session,
    try_award_point,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username):
    """Onboarded user — required so OnboardingRequiredMiddleware lets API calls through."""
    return make_user(username)


def _make_track(
    creator,
    duration=300,
    title="Test Track",
    status=Track.Status.APPROVED,
    visibility=Track.Visibility.PUBLIC,
):
    """Approved + public by default — a track existing tests can actually
    register plays against. Pass status=/visibility= explicitly for tests
    that specifically cover the not-playable-yet rejection path."""
    return Track.objects.create(
        creator=creator,
        title=title,
        content_type="music",
        duration_seconds=duration,
        status=status,
        visibility=visibility,
    )


def _make_play_event(track, user, ip_hash="abc123", day_key="2026-08-17",
                     created_at=None, point_awarded=False):
    pe = PlayEvent(
        track=track,
        user=user,
        ip_hash=ip_hash,
        ua_hash="",
        day_key=day_key,
        point_awarded=point_awarded,
    )
    pe.save()
    if created_at:
        # Override auto_now_add
        PlayEvent.objects.filter(pk=pe.pk).update(created_at=created_at)
        pe.refresh_from_db()
    return pe


# ---------------------------------------------------------------------------
# PointLedger model tests
# ---------------------------------------------------------------------------

class PointLedgerModelTests(TestCase):
    def setUp(self):
        self.creator = _make_user("creator1")
        UserProfile.objects.get_or_create(user=self.creator)

    def test_total_for_user_sums_delta(self):
        track = _make_track(self.creator)
        pe1 = _make_play_event(track, self.creator, ip_hash="ip1", day_key="2026-08-01")
        pe2 = _make_play_event(track, self.creator, ip_hash="ip2", day_key="2026-08-02")
        PointLedger.objects.create(
            user=self.creator, delta=1,
            reason=PointLedger.Reason.PLAY_REWARD,
            play_event=pe1, track_id_snapshot=track.pk, ip_hash_snapshot="ip1",
        )
        PointLedger.objects.create(
            user=self.creator, delta=1,
            reason=PointLedger.Reason.PLAY_REWARD,
            play_event=pe2, track_id_snapshot=track.pk, ip_hash_snapshot="ip2",
        )
        self.assertEqual(PointLedger.total_for_user(self.creator), 2)

    def test_total_for_user_zero_when_empty(self):
        self.assertEqual(PointLedger.total_for_user(self.creator), 0)

    def test_blocked_entry_has_delta_zero(self):
        track = _make_track(self.creator)
        entry = PointLedger.objects.create(
            user=self.creator, delta=0,
            reason=PointLedger.Reason.BLOCKED_TIME,
            play_event=None, track_id_snapshot=track.pk, ip_hash_snapshot="ip1",
            note="too fast",
        )
        self.assertEqual(entry.delta, 0)
        self.assertEqual(PointLedger.total_for_user(self.creator), 0)


# ---------------------------------------------------------------------------
# try_award_point service tests
# ---------------------------------------------------------------------------

class TryAwardPointTests(TestCase):
    def setUp(self):
        self.listener = _make_user("listener1")
        self.creator = _make_user("creator1")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator, duration=300)

    def _call(self, ip_hash="abc123", day_key="2026-08-17",
              progress=0.9, listener=None):
        return try_award_point(
            track=self.track,
            ip_hash=ip_hash,
            day_key=day_key,
            progress_ratio=progress,
            listener_user=listener or self.listener,
        )

    # --- below threshold ---

    def test_below_threshold_not_awarded(self):
        result = self._call(progress=0.1)
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, "below_threshold")
        self.assertEqual(PointLedger.objects.count(), 0)

    # --- gate 1: no play event ---

    def test_no_play_event_blocked(self):
        result = self._call(progress=0.9)
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_NO_EVENT)
        entry = PointLedger.objects.get()
        self.assertEqual(entry.delta, 0)

    # --- gate 2: duplicate ---

    def test_already_awarded_blocked(self):
        _make_play_event(self.track, self.listener, point_awarded=True)
        result = self._call()
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_DUPLICATE)
        self.assertEqual(PointLedger.objects.count(), 0)

    # --- gate 3: time gate ---

    def test_time_gate_blocks_too_fast(self):
        # Play event created just now, track is 300s — need 150s elapsed
        _make_play_event(
            self.track, self.listener,
            created_at=datetime.now(UTC),
        )
        result = self._call(progress=0.9)
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_TIME)
        # Ledger entry with delta=0
        entry = PointLedger.objects.get()
        self.assertEqual(entry.delta, 0)
        # FraudFlag created
        self.assertTrue(FraudFlag.objects.filter(
            flag_type=FraudFlag.FlagType.TIME_FRAUD
        ).exists())

    def test_time_gate_passes_after_enough_time(self):
        # Play event created 200s ago, track is 300s, need 150s
        past = datetime.now(UTC) - timedelta(seconds=200)
        _make_play_event(self.track, self.listener, created_at=past)
        result = self._call(progress=0.9)
        self.assertTrue(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.PLAY_REWARD)

    def test_time_gate_skipped_for_zero_duration_track(self):
        """Tracks with unknown duration (0) skip the time gate."""
        self.track.duration_seconds = 0
        self.track.save()
        _make_play_event(
            self.track, self.listener,
            created_at=datetime.now(UTC),
        )
        result = self._call(progress=0.9)
        self.assertTrue(result.awarded)

    # --- gate 4: IP daily cap ---

    def test_ip_daily_cap_blocks_excess(self):
        from .services import _DEFAULT_IP_DAILY_AWARD_CAP
        # Fill the ledger with cap entries for this IP
        for i in range(_DEFAULT_IP_DAILY_AWARD_CAP):
            PointLedger.objects.create(
                user=self.creator, delta=1,
                reason=PointLedger.Reason.PLAY_REWARD,
                play_event=None,
                track_id_snapshot=self.track.pk,
                ip_hash_snapshot="abc123",
            )
        past = datetime.now(UTC) - timedelta(seconds=200)
        _make_play_event(self.track, self.listener, created_at=past)
        result = self._call(progress=0.9)
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_IP_LIMIT)

    # --- happy path ---

    def test_successful_award(self):
        past = datetime.now(UTC) - timedelta(seconds=200)
        _make_play_event(self.track, self.listener, created_at=past)
        result = self._call(progress=0.9)
        self.assertTrue(result.awarded)
        # Ledger entry with delta=1
        entry = PointLedger.objects.get()
        self.assertEqual(entry.delta, 1)
        self.assertEqual(entry.reason, PointLedger.Reason.PLAY_REWARD)
        # PlayEvent flagged
        pe = PlayEvent.objects.get()
        self.assertTrue(pe.point_awarded)
        # UserProfile.points incremented
        profile = UserProfile.objects.get(user=self.creator)
        self.assertEqual(profile.points, 1)

    def test_idempotent_second_call_does_not_double_award(self):
        past = datetime.now(UTC) - timedelta(seconds=200)
        _make_play_event(self.track, self.listener, created_at=past)
        self._call(progress=0.9)
        result2 = self._call(progress=0.9)
        self.assertFalse(result2.awarded)
        self.assertEqual(PointLedger.objects.filter(delta=1).count(), 1)
        profile = UserProfile.objects.get(user=self.creator)
        self.assertEqual(profile.points, 1)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class RegisterPlayViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # register_play rate-limits by IP via cache
        self.listener = _make_user("listener2")
        self.creator = _make_user("creator2")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator)
        self.client.login(username="listener2", password="pass12345")

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_requires_auth(self):
        self.client.logout()
        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 401)

    def test_missing_track_id(self):
        resp = self.client.post(reverse("api_play"), {})
        self.assertEqual(resp.status_code, 400)

    def test_valid_play_creates_event(self):
        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["counted"])
        self.assertEqual(PlayEvent.objects.count(), 1)

    def test_duplicate_play_not_double_counted(self):
        self.client.post(reverse("api_play"), {"track_id": self.track.id})
        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["counted"])
        self.assertEqual(PlayEvent.objects.count(), 1)

    def test_only_post_allowed(self):
        resp = self.client.get(reverse("api_play"))
        self.assertEqual(resp.status_code, 405)

    def test_draft_track_rejected(self):
        draft = _make_track(self.creator, status=Track.Status.DRAFT, title="Draft")
        resp = self.client.post(reverse("api_play"), {"track_id": draft.id})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"], "track_not_playable")
        self.assertFalse(PlayEvent.objects.filter(track=draft).exists())

    def test_private_approved_track_rejected(self):
        private = _make_track(
            self.creator,
            status=Track.Status.APPROVED,
            visibility=Track.Visibility.PRIVATE,
            title="Private",
        )
        resp = self.client.post(reverse("api_play"), {"track_id": private.id})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(PlayEvent.objects.filter(track=private).exists())

    def test_unlisted_approved_track_is_playable(self):
        unlisted = _make_track(
            self.creator,
            status=Track.Status.APPROVED,
            visibility=Track.Visibility.UNLISTED,
            title="Unlisted",
        )
        resp = self.client.post(reverse("api_play"), {"track_id": unlisted.id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["counted"])

    def test_crossing_a_milestone_notifies_creator(self):
        """Regression: notifications.services.check_and_notify_milestone
        existed since the Notification app was built but was never called
        from anywhere — dead code. register_play is the one place play_count
        actually changes, so it's the correct call site (Phase 3)."""
        from notifications.models import Notification

        self.track.play_count = 99
        self.track.save(update_fields=["play_count"])

        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["play_count"], 100)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator, verb="milestone_plays", track=self.track,
                extra__milestone=100,
            ).exists()
        )

    def test_not_crossing_a_milestone_does_not_notify(self):
        from notifications.models import Notification

        self.track.play_count = 50
        self.track.save(update_fields=["play_count"])

        self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertFalse(
            Notification.objects.filter(recipient=self.creator, verb="milestone_plays").exists()
        )


class SameIpDifferentUsersPlayEventTests(TestCase):
    """Regression: PlayEvent uniqueness used to be (track, ip_hash, day_key)
    only, so two different logged-in listeners sharing an IP (office, campus
    Wi-Fi, mobile CGNAT) would silently collapse into a single PlayEvent —
    the second listener's play was dropped entirely, not just uncounted for
    points. Uniqueness now includes `user` (plays/models.py)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.creator = _make_user("shared_ip_creator")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator)
        self.listener_a = _make_user("shared_ip_listener_a")
        self.listener_b = _make_user("shared_ip_listener_b")

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_two_users_same_ip_each_get_a_play_event(self):
        # Django's test client defaults every request to REMOTE_ADDR="127.0.0.1"
        # — both logins below share that IP without any extra setup.
        self.client.login(username="shared_ip_listener_a", password="pass12345")
        resp_a = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertTrue(resp_a.json()["counted"])
        self.client.logout()

        self.client.login(username="shared_ip_listener_b", password="pass12345")
        resp_b = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertTrue(resp_b.json()["counted"])

        self.assertEqual(PlayEvent.objects.filter(track=self.track).count(), 2)
        self.assertEqual(
            set(PlayEvent.objects.filter(track=self.track).values_list("user_id", flat=True)),
            {self.listener_a.id, self.listener_b.id},
        )

    def test_same_user_twice_same_ip_still_deduped(self):
        self.client.login(username="shared_ip_listener_a", password="pass12345")
        self.client.post(reverse("api_play"), {"track_id": self.track.id})
        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertFalse(resp.json()["counted"])
        self.assertEqual(PlayEvent.objects.filter(track=self.track).count(), 1)


class GetClientIpTests(TestCase):
    """get_client_ip must ignore X-Forwarded-For unless TRUST_PROXY_HEADERS
    is explicitly enabled — trusting it unconditionally would let any
    visitor spoof their IP and defeat the fraud-signal/dedup logic above."""

    def test_ignores_forwarded_header_by_default(self):
        from django.test import RequestFactory

        from .utils import get_client_ip

        req = RequestFactory().get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1"
        )
        self.assertEqual(get_client_ip(req), "10.0.0.1")

    def test_uses_forwarded_header_when_trusted(self):
        from django.test import RequestFactory, override_settings

        from .utils import get_client_ip

        req = RequestFactory().get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1"
        )
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(get_client_ip(req), "1.2.3.4")

    def test_falls_back_to_remote_addr_when_trusted_but_header_absent(self):
        from django.test import RequestFactory, override_settings

        from .utils import get_client_ip

        req = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(get_client_ip(req), "10.0.0.1")


class RegisterProgressViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.listener = _make_user("listener3")
        self.creator = _make_user("creator3")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator, duration=300)
        self.client.login(username="listener3", password="pass12345")

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_requires_auth(self):
        self.client.logout()
        resp = self.client.post(
            reverse("api_play_progress"),
            {"track_id": self.track.id, "progress": 0.9},
        )
        self.assertEqual(resp.status_code, 401)

    def test_missing_params(self):
        resp = self.client.post(reverse("api_play_progress"), {})
        self.assertEqual(resp.status_code, 400)

    def test_bad_progress_value(self):
        resp = self.client.post(
            reverse("api_play_progress"),
            {"track_id": self.track.id, "progress": "not_a_number"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_progress_normalises_percent(self):
        """Frontend sending 90 (percent) should be treated as 0.9.

        This is a full round-trip test: we register the play through the real
        endpoint so the PlayEvent carries the same ip_hash/day_key the
        progress endpoint will compute. Building the PlayEvent by hand with a
        fake ip_hash makes gate 1 fail with BLOCKED_NO_EVENT.
        """
        # 1. Register the play through the API (real ip_hash + day_key)
        resp = self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 200)

        # 2. Backdate it so the time gate (needs 150s for a 300s track) passes
        past = datetime.now(UTC) - timedelta(seconds=200)
        PlayEvent.objects.filter(track=self.track).update(created_at=past)

        # 3. Report progress as a percent value
        resp = self.client.post(
            reverse("api_play_progress"),
            {"track_id": self.track.id, "progress": "90"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["awarded"], data)
        self.assertEqual(data["reason"], PointLedger.Reason.PLAY_REWARD)

    def test_draft_track_rejected_no_point_awarded(self):
        draft = _make_track(self.creator, duration=300, status=Track.Status.DRAFT, title="Draft")
        resp = self.client.post(
            reverse("api_play_progress"), {"track_id": draft.id, "progress": 0.9}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PointLedger.objects.filter(user=self.creator).count(), 0)

    def test_private_track_rejected_no_point_awarded(self):
        private = _make_track(
            self.creator,
            duration=300,
            status=Track.Status.APPROVED,
            visibility=Track.Visibility.PRIVATE,
            title="Private",
        )
        resp = self.client.post(
            reverse("api_play_progress"), {"track_id": private.id, "progress": 0.9}
        )
        self.assertEqual(resp.status_code, 403)


class AggregateStatsCommandTests(TestCase):
    """plays/management/commands/aggregate_stats.py — had 0% coverage.
    Not currently wired to any scheduler (documented as a deliberate,
    not-yet-needed optimization in the Phase 4/5 delivery notes), but it's
    reachable, real code an operator could run — it deserves a basic
    correctness check like anything else in the codebase."""

    def setUp(self):
        self.creator = make_user("agg_creator")
        self.track = _make_track(self.creator, title="Agg")
        self.day = "2026-08-01"

    def _run(self, **kwargs):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("aggregate_stats", date=self.day, stdout=out, **kwargs)
        return out.getvalue()

    def test_aggregates_plays_and_unique_plays_for_the_given_day(self):
        # PlayEvent has a UniqueConstraint on (track, ip_hash, day_key), so
        # "plays" and "unique_plays" are necessarily equal at this level —
        # that's a property of the source data, not something this test
        # should paper over. Two distinct IPs on the same day/track:
        _make_play_event(self.track, self.creator, ip_hash="ip1", day_key=self.day, point_awarded=True)
        _make_play_event(self.track, self.creator, ip_hash="ip2", day_key=self.day)

        self._run()

        stat = DailyTrackStat.objects.get(track=self.track, day=self.day)
        self.assertEqual(stat.plays, 2)
        self.assertEqual(stat.unique_plays, 2)

    def test_points_awarded_counts_actual_awards_not_just_authenticated_plays(self):
        """Regression (S11): the old query filtered on `user__isnull=False`,
        which is always true (every write path requires auth) and so always
        equalled `plays` regardless of whether a point was actually awarded.
        It must count point_awarded=True specifically."""
        _make_play_event(self.track, self.creator, ip_hash="ip1", day_key=self.day, point_awarded=True)
        _make_play_event(self.track, self.creator, ip_hash="ip2", day_key=self.day, point_awarded=False)
        _make_play_event(self.track, self.creator, ip_hash="ip3", day_key=self.day, point_awarded=False)

        self._run()

        stat = DailyTrackStat.objects.get(track=self.track, day=self.day)
        self.assertEqual(stat.plays, 3)
        self.assertEqual(stat.points_awarded, 1)

    def test_rerunning_the_same_day_updates_in_place_not_duplicates(self):
        _make_play_event(self.track, self.creator, ip_hash="ip1", day_key=self.day)
        self._run()
        _make_play_event(self.track, self.creator, ip_hash="ip2", day_key=self.day)
        self._run()

        self.assertEqual(DailyTrackStat.objects.filter(track=self.track, day=self.day).count(), 1)
        stat = DailyTrackStat.objects.get(track=self.track, day=self.day)
        self.assertEqual(stat.plays, 2)

    def test_invalid_date_raises_command_error(self):
        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError):
            call_command("aggregate_stats", date="not-a-date")
        self.assertEqual(PointLedger.objects.filter(user=self.creator).count(), 0)


# ---------------------------------------------------------------------------
# PlaybackSession (S11) — model + service lifecycle
# ---------------------------------------------------------------------------

class PlaybackSessionServiceTests(TestCase):
    """start_playback_session() and try_award_point()'s session bookkeeping."""

    def setUp(self):
        self.listener = _make_user("ps_listener")
        self.creator = _make_user("ps_creator")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator, duration=300)

    def test_start_playback_session_creates_open_row(self):
        session = start_playback_session(
            track=self.track, user=self.listener, ip_hash="ip1", ua_hash="ua1",
        )
        self.assertEqual(session.status, PlaybackSession.Status.OPEN)
        self.assertEqual(session.source, "web")
        self.assertIsNone(session.ended_at)
        self.assertEqual(session.max_progress_ratio, 0.0)

    def test_register_play_creates_a_session_even_when_deduped(self):
        """Each register_play() call must produce a PlaybackSession — even
        the second, deduped call — because fraud-burst detection needs
        attempt-level granularity that PlayEvent's daily dedup erases."""
        from django.core.cache import cache

        cache.clear()
        self.client.login(username="ps_listener", password="pass12345")
        self.client.post(reverse("api_play"), {"track_id": self.track.id})
        self.client.post(reverse("api_play"), {"track_id": self.track.id})
        cache.clear()

        self.assertEqual(PlaybackSession.objects.filter(track=self.track).count(), 2)
        self.assertEqual(PlayEvent.objects.filter(track=self.track).count(), 1)

    def test_progress_reuses_the_open_session_not_a_new_one(self):
        session = start_playback_session(
            track=self.track, user=self.listener, ip_hash="ip1", ua_hash="",
        )
        past = datetime.now(UTC) - timedelta(seconds=200)
        _make_play_event(self.track, self.listener, ip_hash="ip1", created_at=past)

        try_award_point(
            track=self.track, ip_hash="ip1", day_key="2026-08-17",
            progress_ratio=0.9, listener_user=self.listener,
        )

        self.assertEqual(PlaybackSession.objects.filter(track=self.track).count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.status, PlaybackSession.Status.QUALIFIED)
        self.assertIsNotNone(session.ended_at)
        self.assertAlmostEqual(session.max_progress_ratio, 0.9)

    def test_progress_without_any_session_creates_a_flagged_fallback(self):
        """A progress report with no prior register_play() call at all is
        itself suspicious (broken client or direct API probing) — mirrors
        the existing BLOCKED_NO_EVENT gate, but at the session level."""
        result = try_award_point(
            track=self.track, ip_hash="ip1", day_key="2026-08-17",
            progress_ratio=0.9, listener_user=self.listener,
        )
        self.assertFalse(result.awarded)
        session = PlaybackSession.objects.get(track=self.track, user=self.listener)
        self.assertEqual(session.source, "progress_fallback")

    def test_below_threshold_progress_still_updates_max_progress_ratio(self):
        start_playback_session(track=self.track, user=self.listener, ip_hash="ip1", ua_hash="")
        try_award_point(
            track=self.track, ip_hash="ip1", day_key="2026-08-17",
            progress_ratio=0.05, listener_user=self.listener,
        )
        session = PlaybackSession.objects.get(track=self.track, user=self.listener)
        self.assertAlmostEqual(session.max_progress_ratio, 0.05)
        self.assertEqual(session.status, PlaybackSession.Status.OPEN)

    def test_time_gate_block_flags_the_session(self):
        session = start_playback_session(
            track=self.track, user=self.listener, ip_hash="ip1", ua_hash="",
        )
        _make_play_event(
            self.track, self.listener, ip_hash="ip1",
            created_at=datetime.now(UTC),  # too recent -> time gate blocks
        )
        try_award_point(
            track=self.track, ip_hash="ip1", day_key="2026-08-17",
            progress_ratio=0.9, listener_user=self.listener,
        )
        session.refresh_from_db()
        self.assertEqual(session.status, PlaybackSession.Status.FLAGGED)
        self.assertEqual(session.disqualify_reason, PointLedger.Reason.BLOCKED_TIME)


# ---------------------------------------------------------------------------
# Anti-fraud signals (S11) — evaluate_fraud_signals() via try_award_point
# ---------------------------------------------------------------------------

class FraudSignalTests(TestCase):
    def setUp(self):
        self.listener = _make_user("fraud_listener")
        self.creator = _make_user("fraud_creator")
        UserProfile.objects.get_or_create(user=self.creator)
        self.track = _make_track(self.creator, duration=10)  # short track, fast gates

    def _play_and_progress(self, ip_hash, progress=0.9, elapsed_seconds=10):
        past = datetime.now(UTC) - timedelta(seconds=elapsed_seconds)
        session = start_playback_session(
            track=self.track, user=self.listener, ip_hash=ip_hash, ua_hash="",
        )
        _make_play_event(self.track, self.listener, ip_hash=ip_hash, created_at=past)
        result = try_award_point(
            track=self.track, ip_hash=ip_hash, day_key="2026-08-17",
            progress_ratio=progress, listener_user=self.listener,
        )
        return session, result

    def test_normal_single_play_is_not_flagged(self):
        session, result = self._play_and_progress("ip_normal")
        self.assertTrue(result.awarded)
        self.assertFalse(FraudFlag.objects.filter(flag_type=FraudFlag.FlagType.PLAY_BURST).exists())

    def test_ip_burst_hard_threshold_blocks_award(self):
        from .services import _BURST_HARD_THRESHOLD

        # Flood PlaybackSession rows from the same IP to cross the hard
        # threshold before the real award attempt.
        for _ in range(_BURST_HARD_THRESHOLD):
            PlaybackSession.objects.create(
                track=self.track, user=self.listener, ip_hash="ip_burst", ua_hash="",
            )
        _, result = self._play_and_progress("ip_burst")
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_FRAUD_SIGNAL)
        self.assertTrue(FraudFlag.objects.filter(
            ip_hash="ip_burst", flag_type=FraudFlag.FlagType.PLAY_BURST
        ).exists())

    def test_ip_burst_soft_threshold_flags_but_still_awards(self):
        from .services import _BURST_HARD_THRESHOLD, _BURST_SOFT_THRESHOLD

        count = (_BURST_SOFT_THRESHOLD + _BURST_HARD_THRESHOLD) // 2
        for _ in range(count):
            PlaybackSession.objects.create(
                track=self.track, user=self.listener, ip_hash="ip_soft", ua_hash="",
            )
        _, result = self._play_and_progress("ip_soft")
        self.assertTrue(result.awarded)
        self.assertTrue(FraudFlag.objects.filter(
            ip_hash="ip_soft", flag_type=FraudFlag.FlagType.PLAY_BURST
        ).exists())

    def test_repeated_short_sessions_block_award(self):
        """Three prior sessions that ended almost instantly (bot-like replay
        spam) should hard-block the next award attempt for this listener."""
        now = dj_timezone.now()
        for i in range(3):
            PlaybackSession.objects.create(
                track=self.track, user=self.listener, ip_hash=f"ip_short_{i}", ua_hash="",
                status=PlaybackSession.Status.FLAGGED,
                started_at=now, ended_at=now + timedelta(seconds=1),
            )
        _, result = self._play_and_progress("ip_new")
        self.assertFalse(result.awarded)
        self.assertEqual(result.reason, PointLedger.Reason.BLOCKED_FRAUD_SIGNAL)

    def test_long_normal_sessions_do_not_trigger_short_session_block(self):
        now = dj_timezone.now()
        for i in range(3):
            PlaybackSession.objects.create(
                track=self.track, user=self.listener, ip_hash=f"ip_norm_{i}", ua_hash="",
                status=PlaybackSession.Status.QUALIFIED,
                started_at=now, ended_at=now + timedelta(minutes=2),
            )
        _, result = self._play_and_progress("ip_final")
        self.assertTrue(result.awarded)


# ---------------------------------------------------------------------------
# aggregate_daily_stats() service function (S11)
# ---------------------------------------------------------------------------

class AggregateDailyStatsServiceTests(TestCase):
    def setUp(self):
        self.creator = make_user("agg_svc_creator")
        self.track = _make_track(self.creator, title="AggSvc")

    def test_returns_number_of_track_rows_written(self):
        day = dj_timezone.localdate() - timedelta(days=5)
        _make_play_event(self.track, self.creator, ip_hash="ipx", day_key=day.isoformat())
        written = aggregate_daily_stats(day)
        self.assertEqual(written, 1)
        self.assertTrue(DailyTrackStat.objects.filter(track=self.track, day=day).exists())


# ---------------------------------------------------------------------------
# get_creator_stats_series() — DailyTrackStat-backed dashboard series (S11)
# ---------------------------------------------------------------------------

class GetCreatorStatsSeriesTests(TestCase):
    def setUp(self):
        self.creator = make_user("stats_creator")
        self.other_creator = make_user("stats_other")
        self.track = _make_track(self.creator, title="StatsTrack")
        self.other_track = _make_track(self.other_creator, title="OtherTrack")

    def test_daily_series_is_zero_filled_for_days_with_no_data(self):
        series = get_creator_stats_series(creator=self.creator, granularity="daily")
        self.assertEqual(len(series), 30)
        self.assertTrue(all(row["plays"] == 0 for row in series))

    def test_daily_series_reflects_historical_dailytrackstat_row(self):
        day = dj_timezone.localdate() - timedelta(days=3)
        DailyTrackStat.objects.create(track=self.track, day=day, plays=7, unique_plays=5, points_awarded=2)

        series = get_creator_stats_series(creator=self.creator, granularity="daily")
        row = next(r for r in series if r["label"] == day.isoformat())
        self.assertEqual(row["plays"], 7)
        self.assertEqual(row["points"], 2)

    def test_today_is_computed_live_not_from_a_stale_dailytrackstat_row(self):
        """DailyTrackStat is only ever aggregated for days that already
        ended (plays/tasks.py runs it for "yesterday") — a row for *today*
        should never be trusted, even if one somehow exists."""
        today = dj_timezone.localdate()
        DailyTrackStat.objects.create(track=self.track, day=today, plays=999, unique_plays=999, points_awarded=999)
        _make_play_event(self.track, self.creator, ip_hash="ip_today", day_key=today.isoformat(), point_awarded=True)

        series = get_creator_stats_series(creator=self.creator, granularity="daily")
        row = next(r for r in series if r["label"] == today.isoformat())
        self.assertEqual(row["plays"], 1)
        self.assertEqual(row["points"], 1)

    def test_other_creators_tracks_are_excluded(self):
        day = dj_timezone.localdate() - timedelta(days=2)
        DailyTrackStat.objects.create(track=self.other_track, day=day, plays=50, unique_plays=50, points_awarded=10)

        series = get_creator_stats_series(creator=self.creator, granularity="daily")
        row = next(r for r in series if r["label"] == day.isoformat())
        self.assertEqual(row["plays"], 0)

    def test_weekly_granularity_sums_days_into_buckets(self):
        today = dj_timezone.localdate()
        DailyTrackStat.objects.create(track=self.track, day=today - timedelta(days=1), plays=3, unique_plays=3, points_awarded=1)
        DailyTrackStat.objects.create(track=self.track, day=today - timedelta(days=2), plays=4, unique_plays=4, points_awarded=2)

        series = get_creator_stats_series(creator=self.creator, granularity="weekly")
        self.assertEqual(sum(row["plays"] for row in series), 7)
        self.assertEqual(sum(row["points"] for row in series), 3)

    def test_monthly_granularity_groups_by_calendar_month(self):
        series = get_creator_stats_series(creator=self.creator, granularity="monthly")
        self.assertTrue(len(series) >= 1)
        for row in series:
            self.assertRegex(row["label"], r"^\d{4}-\d{2}$")

    def test_unknown_granularity_falls_back_to_daily(self):
        series = get_creator_stats_series(creator=self.creator, granularity="yearly")
        self.assertEqual(len(series), 30)


# ---------------------------------------------------------------------------
# api_creator_stats view (S11)
# ---------------------------------------------------------------------------

class ApiCreatorStatsViewTests(TestCase):
    def setUp(self):
        self.creator = _make_user("api_stats_creator")
        self.track = _make_track(self.creator, title="ApiStatsTrack")

    def test_requires_auth(self):
        resp = self.client.get(reverse("api_creator_stats"))
        self.assertEqual(resp.status_code, 401)

    def test_default_range_is_daily(self):
        self.client.login(username="api_stats_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_stats"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["range"], "daily")
        self.assertEqual(len(data["series"]), 30)

    def test_weekly_range_param(self):
        self.client.login(username="api_stats_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_stats"), {"range": "weekly"})
        self.assertEqual(resp.json()["range"], "weekly")

    def test_invalid_range_falls_back_to_daily(self):
        self.client.login(username="api_stats_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_stats"), {"range": "bogus"})
        self.assertEqual(resp.json()["range"], "daily")

    def test_only_shows_the_logged_in_creators_own_tracks(self):
        other = _make_user("api_stats_other")
        other_track = _make_track(other, title="OtherApiTrack")
        day = dj_timezone.localdate() - timedelta(days=1)
        DailyTrackStat.objects.create(track=other_track, day=day, plays=99, unique_plays=99, points_awarded=99)

        self.client.login(username="api_stats_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_stats"))
        row = next(r for r in resp.json()["series"] if r["label"] == day.isoformat())
        self.assertEqual(row["plays"], 0)


# ---------------------------------------------------------------------------
# aggregate_yesterday_track_stats Celery task (S11)
# ---------------------------------------------------------------------------

class AggregateYesterdayTrackStatsTaskTests(TestCase):
    """CELERY_TASK_ALWAYS_EAGER runs .delay() in-process in dev/test (see
    plays/tasks.py docstring) — the beat schedule itself is never exercised
    here, only that the task correctly aggregates "yesterday"."""

    def test_aggregates_yesterdays_playevents(self):
        from .tasks import aggregate_yesterday_track_stats

        creator = make_user("task_creator")
        track = _make_track(creator, title="TaskTrack")
        yesterday = dj_timezone.localdate() - timedelta(days=1)
        _make_play_event(track, creator, ip_hash="ipy", day_key=yesterday.isoformat(), point_awarded=True)

        written = aggregate_yesterday_track_stats()

        self.assertEqual(written, 1)
        stat = DailyTrackStat.objects.get(track=track, day=yesterday)
        self.assertEqual(stat.plays, 1)
        self.assertEqual(stat.points_awarded, 1)


# ---------------------------------------------------------------------------
# plays/geo.py — device/country resolution (S12)
# ---------------------------------------------------------------------------

class ResolveDeviceTypeTests(TestCase):
    def test_empty_user_agent_is_unknown(self):
        self.assertEqual(resolve_device_type(""), PlaybackSession.DeviceType.UNKNOWN)
        self.assertEqual(resolve_device_type(None), PlaybackSession.DeviceType.UNKNOWN)

    def test_iphone_is_mobile(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.MOBILE)

    def test_android_with_mobile_token_is_mobile(self):
        ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.MOBILE)

    def test_ipad_is_tablet(self):
        ua = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Safari/605.1.15"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.TABLET)

    def test_android_without_mobile_token_is_tablet(self):
        ua = "Mozilla/5.0 (Linux; Android 14; SM-X200) AppleWebKit/537.36 Safari/537.36"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.TABLET)

    def test_desktop_chrome_is_desktop(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.DESKTOP)

    def test_known_bot_is_bot(self):
        ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        self.assertEqual(resolve_device_type(ua), PlaybackSession.DeviceType.BOT)


class ResolveCountryCodeTests(TestCase):
    def _req(self, **meta):
        from django.test import RequestFactory
        return RequestFactory().get("/", **meta)

    def test_untrusted_proxy_headers_returns_empty(self):
        """TRUST_PROXY_HEADERS defaults to off — a header must never be
        trusted just because it's present, mirroring plays/utils.py's
        X-Forwarded-For gate."""
        req = self._req(HTTP_CF_IPCOUNTRY="IR")
        self.assertEqual(resolve_country_code(req), "")

    def test_trusted_cloudflare_header_is_used(self):
        from django.test import override_settings

        req = self._req(HTTP_CF_IPCOUNTRY="ir")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(resolve_country_code(req), "IR")

    def test_trusted_generic_header_is_used_when_cloudflare_absent(self):
        from django.test import override_settings

        req = self._req(HTTP_X_COUNTRY_CODE="DE")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(resolve_country_code(req), "DE")

    def test_implausible_header_value_is_rejected(self):
        from django.test import override_settings

        req = self._req(HTTP_CF_IPCOUNTRY="XX; DROP TABLE users")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(resolve_country_code(req), "")

    def test_missing_header_returns_empty_even_when_trusted(self):
        from django.test import override_settings

        req = self._req()
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(resolve_country_code(req), "")


# ---------------------------------------------------------------------------
# register_play/register_progress wiring for country/device (S12)
# ---------------------------------------------------------------------------

class RegisterPlayGeoDeviceWiringTests(TestCase):
    def setUp(self):
        self.creator = _make_user("wire_creator")
        self.track = _make_track(self.creator)

    def test_register_play_stores_resolved_device_type(self):
        self.client.login(username="wire_creator", password="pass12345")
        self.client.post(
            reverse("api_play"), {"track_id": self.track.id},
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148",
        )
        session = PlaybackSession.objects.filter(track=self.track).latest("started_at")
        self.assertEqual(session.device_type, PlaybackSession.DeviceType.MOBILE)
        self.assertEqual(session.country_code, "")  # TRUST_PROXY_HEADERS off in tests

    def test_register_play_stores_country_only_when_proxy_trusted(self):
        from django.test import override_settings

        self.client.login(username="wire_creator", password="pass12345")
        with override_settings(TRUST_PROXY_HEADERS=True):
            self.client.post(
                reverse("api_play"), {"track_id": self.track.id},
                HTTP_CF_IPCOUNTRY="IR",
            )
        session = PlaybackSession.objects.filter(track=self.track).latest("started_at")
        self.assertEqual(session.country_code, "IR")


# ---------------------------------------------------------------------------
# get_creator_geo_device_breakdown() service (S12)
# ---------------------------------------------------------------------------

class GetCreatorGeoDeviceBreakdownTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.creator = make_user("geo_creator")
        self.other_creator = make_user("geo_other")
        self.track = _make_track(self.creator, title="GeoTrack")
        self.other_track = _make_track(self.other_creator, title="OtherGeoTrack")

    def _session(self, track, **kw):
        defaults = dict(track=track, user=self.creator, ip_hash="ip1", ua_hash="ua1")
        defaults.update(kw)
        return PlaybackSession.objects.create(**defaults)

    def test_counts_are_grouped_by_country_and_device(self):
        self._session(self.track, country_code="IR", device_type=PlaybackSession.DeviceType.MOBILE)
        self._session(self.track, country_code="IR", device_type=PlaybackSession.DeviceType.DESKTOP)
        self._session(self.track, country_code="DE", device_type=PlaybackSession.DeviceType.MOBILE)

        result = get_creator_geo_device_breakdown(self.creator)

        countries = {row["code"]: row["count"] for row in result["countries"]}
        self.assertEqual(countries, {"IR": 2, "DE": 1})
        devices = {row["type"]: row["count"] for row in result["devices"]}
        self.assertEqual(devices["mobile"], 2)
        self.assertEqual(devices["desktop"], 1)

    def test_empty_country_code_counted_as_unknown_not_a_country_row(self):
        self._session(self.track, country_code="", device_type=PlaybackSession.DeviceType.DESKTOP)
        result = get_creator_geo_device_breakdown(self.creator)
        self.assertEqual(result["unknown_country_count"], 1)
        self.assertEqual(result["countries"], [])

    def test_other_creators_sessions_are_excluded(self):
        self._session(self.other_track, user=self.other_creator, country_code="US")
        result = get_creator_geo_device_breakdown(self.creator)
        self.assertEqual(result["countries"], [])
        self.assertEqual(result["unknown_country_count"], 0)

    def test_sessions_outside_the_window_are_excluded(self):
        from django.utils import timezone as tz
        old = self._session(self.track, country_code="IR")
        PlaybackSession.objects.filter(pk=old.pk).update(
            started_at=tz.now() - timedelta(days=90)
        )
        result = get_creator_geo_device_breakdown(self.creator, days=30)
        self.assertEqual(result["countries"], [])

    def test_response_never_contains_raw_hash_fields(self):
        """Constitution/privacy: only aggregate counts leave this function —
        never a raw ip_hash/ua_hash value or a per-session row."""
        self._session(self.track, country_code="IR", ip_hash="super-secret-ip-hash")
        result = get_creator_geo_device_breakdown(self.creator)
        blob = str(result)
        self.assertNotIn("super-secret-ip-hash", blob)
        self.assertNotIn("ip_hash", blob)
        self.assertNotIn("ua_hash", blob)

    def test_result_is_cached_between_calls(self):
        self._session(self.track, country_code="IR")
        first = get_creator_geo_device_breakdown(self.creator)
        # A session created after the first (cached) call must NOT change
        # the second call's result within the TTL window.
        self._session(self.track, country_code="IR")
        second = get_creator_geo_device_breakdown(self.creator)
        self.assertEqual(first, second)
        self.assertEqual(second["countries"][0]["count"], 1)


# ---------------------------------------------------------------------------
# api_creator_geo_device view (S12)
# ---------------------------------------------------------------------------

class ApiCreatorGeoDeviceViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.creator = _make_user("api_geo_creator")
        self.track = _make_track(self.creator, title="ApiGeoTrack")

    def test_requires_auth(self):
        resp = self.client.get(reverse("api_creator_geo_device"))
        self.assertEqual(resp.status_code, 401)

    def test_returns_aggregate_breakdown_for_own_tracks(self):
        PlaybackSession.objects.create(
            track=self.track, user=self.creator, ip_hash="ip1", ua_hash="ua1",
            country_code="IR", device_type=PlaybackSession.DeviceType.MOBILE,
        )
        self.client.login(username="api_geo_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_geo_device"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["countries"], [{"code": "IR", "count": 1}])
        self.assertEqual(data["devices"][0]["type"], "mobile")

    def test_response_body_never_leaks_raw_ip_or_ua_hash(self):
        PlaybackSession.objects.create(
            track=self.track, user=self.creator,
            ip_hash="leak-me-ip-hash-value", ua_hash="leak-me-ua-hash-value",
            country_code="IR",
        )
        self.client.login(username="api_geo_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_geo_device"))
        body = resp.content.decode()
        self.assertNotIn("leak-me-ip-hash-value", body)
        self.assertNotIn("leak-me-ua-hash-value", body)
        self.assertNotIn("ip_hash", body)
        self.assertNotIn("ua_hash", body)

    def test_days_param_is_clamped(self):
        self.client.login(username="api_geo_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_geo_device"), {"days": "99999"})
        self.assertEqual(resp.json()["days"], 365)
        resp = self.client.get(reverse("api_creator_geo_device"), {"days": "-5"})
        self.assertEqual(resp.json()["days"], 1)

    def test_only_shows_the_logged_in_creators_own_tracks(self):
        other = _make_user("api_geo_other")
        other_track = _make_track(other, title="OtherApiGeoTrack")
        PlaybackSession.objects.create(
            track=other_track, user=other, ip_hash="ip1", ua_hash="ua1", country_code="FR",
        )
        self.client.login(username="api_geo_creator", password="pass12345")
        resp = self.client.get(reverse("api_creator_geo_device"))
        self.assertEqual(resp.json()["countries"], [])
