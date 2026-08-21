"""plays/tests.py — Tests for play registration and point award system."""

from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from accounts.models import UserProfile
from core.test_utils import make_user
from tracks.models import Track

from .models import DailyTrackStat, FraudFlag, PlaybackSession, PlayEvent, PointLedger
from .services import start_playback_session, try_award_point

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
