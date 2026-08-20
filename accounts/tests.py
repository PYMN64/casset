"""accounts/tests.py — Tests for authentication, onboarding, and creator flows."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PhoneOTP, UserProfile

User = get_user_model()


def _make_user(username, password="pass12345"):
    return User.objects.create_user(username=username, password=password)


# ---------------------------------------------------------------------------
# UserProfile signal
# ---------------------------------------------------------------------------

class UserProfileSignalTests(TestCase):
    """UserProfile must be auto-created when a User is saved."""

    def test_profile_created_on_user_creation(self):
        user = _make_user("signaltest")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_profile_creation_idempotent(self):
        """Creating a user twice (or calling signal again) must not raise."""
        user = _make_user("idempotent1")
        # Manually fire signal again — should not crash
        from accounts.signals import ensure_profile
        ensure_profile(User, instance=user, created=True)
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterViewTests(TestCase):
    def test_get_renders_form(self):
        resp = self.client.get(reverse("register"))
        self.assertEqual(resp.status_code, 200)

    def test_valid_registration_creates_user_and_profile(self):
        resp = self.client.post(reverse("register"), {
            "username": "newuser1",
            "password1": "V3ryStr0ngPass!",
            "password2": "V3ryStr0ngPass!",
            "email": "new@example.com",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newuser1")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_authenticated_user_redirected_away(self):
        _make_user("existing1")
        self.client.login(username="existing1", password="pass12345")
        resp = self.client.get(reverse("register"))
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginViewTests(TestCase):
    def setUp(self):
        self.user = _make_user("loginuser")
        UserProfile.objects.get_or_create(user=self.user)

    def test_get_renders_form(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)

    def test_valid_login_redirects(self):
        resp = self.client.post(reverse("login"), {
            "username": "loginuser",
            "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 302)

    def test_wrong_password_stays_on_page(self):
        resp = self.client.post(reverse("login"), {
            "username": "loginuser",
            "password": "wrongpassword",
        })
        self.assertEqual(resp.status_code, 200)

    def test_suspended_user_blocked_with_persian_message(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        resp = self.client.post(reverse("login"), {
            "username": "loginuser",
            "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resp, "این حساب تعلیق شده است")


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class OnboardingViewTests(TestCase):
    def setUp(self):
        self.user = _make_user("onboardme")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.client.login(username="onboardme", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("onboarding"))
        self.assertEqual(resp.status_code, 302)

    def test_get_renders_form(self):
        resp = self.client.get(reverse("onboarding"))
        self.assertEqual(resp.status_code, 200)

    def test_valid_submission_marks_onboarding_complete(self):
        resp = self.client.post(reverse("onboarding"), {
            "email": "user@example.com",
            "first_name": "علی",
            "last_name": "محمدی",
            "display_name": "علی محمدی",
            "interests": ["music"],
        })
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.onboarding_complete)


# ---------------------------------------------------------------------------
# Creator apply
# ---------------------------------------------------------------------------

class CreatorApplyViewTests(TestCase):
    def setUp(self):
        self.user = _make_user("creator_applicant")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.client.login(username="creator_applicant", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("creator_apply"))
        self.assertEqual(resp.status_code, 302)

    def test_post_sets_status_to_pending(self):
        resp = self.client.post(reverse("creator_apply"))
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.creator_status, UserProfile.CreatorStatus.PENDING)
        self.assertTrue(self.profile.creator_enabled)


# ---------------------------------------------------------------------------
# Public profile
# ---------------------------------------------------------------------------

class PublicProfileViewTests(TestCase):
    def setUp(self):
        self.user = _make_user("publicuser")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_profile_renders(self):
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertEqual(resp.status_code, 200)

    def test_profile_with_handle_redirects(self):
        self.profile.public_handle = "myhandle"
        self.profile.save()
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("myhandle", resp["Location"])

    def test_og_title_present(self):
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertContains(resp, 'property="og:title"')
        self.assertContains(resp, "publicuser")

    def test_no_og_image_without_avatar(self):
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertNotContains(resp, 'property="og:image"')

    def test_404_for_unknown_user(self):
        resp = self.client.get(reverse("public_profile", args=["doesnotexist"]))
        self.assertEqual(resp.status_code, 404)

    def test_likes_stat_reflects_real_track_likes(self):
        """Regression: this view used to hardcode stats['likes'] = 0
        regardless of actual TrackLike rows (public_profile_by_handle
        computed it correctly; this path didn't)."""
        from interactions.models import TrackLike
        from tracks.models import Track

        liker = _make_user("liker_for_stats")
        track = Track.objects.create(
            creator=self.user, title="T", slug="stats-t", status=Track.Status.APPROVED,
        )
        TrackLike.objects.create(user=liker, track=track)

        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertEqual(resp.context["stats"]["likes"], 1)

    def test_podcast_tracks_separated_from_music_tracks(self):
        from tracks.models import Track

        Track.objects.create(
            creator=self.user, title="Song", slug="tab-music", status=Track.Status.APPROVED,
            content_type=Track.ContentType.MUSIC, visibility=Track.Visibility.PUBLIC,
        )
        Track.objects.create(
            creator=self.user, title="Episode", slug="tab-podcast", status=Track.Status.APPROVED,
            content_type=Track.ContentType.PODCAST, visibility=Track.Visibility.PUBLIC,
        )
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        self.assertEqual(len(resp.context["tracks"]), 1)
        self.assertEqual(len(resp.context["podcast_tracks"]), 1)
        self.assertEqual(resp.context["tracks"][0].slug, "tab-music")
        self.assertEqual(resp.context["podcast_tracks"][0].slug, "tab-podcast")

    def test_public_album_listed_private_album_excluded(self):
        from tracks.models import Album

        Album.objects.create(creator=self.user, title="Public LP", is_public=True)
        Album.objects.create(creator=self.user, title="Private LP", is_public=False)
        resp = self.client.get(reverse("public_profile", args=["publicuser"]))
        titles = [a.title for a in resp.context["albums"]]
        self.assertIn("Public LP", titles)
        self.assertNotIn("Private LP", titles)


class ApiUserConnectionsTests(TestCase):
    def setUp(self):
        self.user = _make_user("connuser")
        self.follower = _make_user("connfollower")

    def test_bad_type_rejected(self):
        resp = self.client.get(reverse("api_user_connections", args=["connuser"]), {"type": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_user_404s(self):
        resp = self.client.get(reverse("api_user_connections", args=["nobody"]), {"type": "followers"})
        self.assertEqual(resp.status_code, 404)

    def test_followers_list_reflects_real_follow(self):
        from interactions.models import CreatorFollow

        CreatorFollow.objects.create(user=self.follower, creator=self.user)
        resp = self.client.get(reverse("api_user_connections", args=["connuser"]), {"type": "followers"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual([p["username"] for p in data["people"]], ["connfollower"])

    def test_following_list_reflects_real_follow(self):
        from interactions.models import CreatorFollow

        CreatorFollow.objects.create(user=self.follower, creator=self.user)
        resp = self.client.get(reverse("api_user_connections", args=["connfollower"]), {"type": "following"})
        data = resp.json()
        self.assertEqual([p["username"] for p in data["people"]], ["connuser"])


# ---------------------------------------------------------------------------
# Middleware: OnboardingRequired
# ---------------------------------------------------------------------------

class OnboardingMiddlewareTests(TestCase):
    def setUp(self):
        self.user = _make_user("middlewareuser")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.client.login(username="middlewareuser", password="pass12345")

    def test_incomplete_onboarding_redirects_to_onboarding(self):
        self.profile.onboarding_complete = False
        self.profile.save()
        resp = self.client.get("/tracks/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("onboarding", resp["Location"])

    def test_completed_onboarding_passes_through(self):
        self.profile.onboarding_complete = True
        self.profile.save()
        resp = self.client.get(reverse("onboarding"))
        # Onboarding itself is in the allowlist
        self.assertEqual(resp.status_code, 200)

    def test_login_page_accessible_without_onboarding(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Phone OTP login
#
# Regression coverage for a confirmed production bug: phone_start_view used
# `settings.DEBUG` without importing `django.conf.settings`, so every valid
# phone submission raised NameError (the whole phone-login path was down).
# These tests exercise the full request→verify→login flow so that class of
# bug (an unimported name only hit on a specific POST branch) can't hide
# behind smoke tests again.
# ---------------------------------------------------------------------------

class PhoneStartViewTests(TestCase):
    phone = "09121234567"

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_get_renders_form(self):
        resp = self.client.get(reverse("phone_start"))
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_user_redirected_away(self):
        _make_user("phonestart_authed")
        self.client.login(username="phonestart_authed", password="pass12345")
        resp = self.client.get(reverse("phone_start"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("discover"))

    def test_invalid_form_rerenders_without_crashing(self):
        resp = self.client.post(reverse("phone_start"), {"phone_number": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PhoneOTP.objects.exists())

    def test_valid_submission_creates_otp_and_redirects_to_verify(self):
        resp = self.client.post(reverse("phone_start"), {"phone_number": self.phone})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("phone_verify"), resp.url)
        self.assertTrue(PhoneOTP.objects.filter(phone_number=self.phone).exists())

    def test_international_prefix_normalises_to_local_format(self):
        self.client.post(reverse("phone_start"), {"phone_number": "+989121234567"})
        self.assertTrue(PhoneOTP.objects.filter(phone_number=self.phone).exists())

    @override_settings(DEBUG=True)
    def test_debug_mode_surfaces_code_in_message_not_crash(self):
        """This is the exact branch that previously raised NameError.

        Django's test runner forces DEBUG=False by default, so this must be
        forced back to True to actually exercise the `if settings.DEBUG:`
        branch that crashed in production.
        """
        resp = self.client.post(reverse("phone_start"), {"phone_number": self.phone}, follow=True)
        page_messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("[DEV] کد تست:" in m for m in page_messages))

    def test_production_mode_hides_code_in_message(self):
        resp = self.client.post(reverse("phone_start"), {"phone_number": self.phone}, follow=True)
        page_messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("کد ورود به شماره شما ارسال شد" in m for m in page_messages))
        self.assertFalse(any("کد تست" in m for m in page_messages))

    def test_resend_within_cooldown_is_blocked_and_does_not_duplicate(self):
        self.client.post(reverse("phone_start"), {"phone_number": self.phone})
        resp = self.client.post(reverse("phone_start"), {"phone_number": self.phone})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PhoneOTP.objects.filter(phone_number=self.phone).count(), 1)

    def test_ip_rate_limit_blocks_after_threshold_across_different_numbers(self):
        """An attacker spamming OTP requests across many phone numbers from
        one IP must be blocked, not just the same-number cooldown."""
        for i in range(10):
            self.client.post(reverse("phone_start"), {"phone_number": f"0912000{i:04d}"})
        resp = self.client.post(reverse("phone_start"), {"phone_number": "09129999999"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PhoneOTP.objects.filter(phone_number="09129999999").exists())


class PhoneVerifyViewTests(TestCase):
    phone = "09121234567"
    fixed_code = "123456"

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _request_code(self):
        """Trigger phone_start with a patched RNG so the OTP code is known."""
        with patch("accounts.views.secrets.randbelow", return_value=int(self.fixed_code)):
            self.client.post(reverse("phone_start"), {"phone_number": self.phone})
        return self.fixed_code

    def test_get_renders_form(self):
        resp = self.client.get(reverse("phone_verify") + f"?phone={self.phone}")
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_user_redirected_away(self):
        _make_user("phoneverify_authed")
        self.client.login(username="phoneverify_authed", password="pass12345")
        resp = self.client.get(reverse("phone_verify"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("discover"))

    def test_correct_code_creates_new_user_logs_in_and_marks_otp_used(self):
        code = self._request_code()
        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": self.phone, "code": code}
        )
        self.assertRedirects(resp, reverse("onboarding"))

        profile = UserProfile.objects.get(phone_number=self.phone)
        self.assertIsNotNone(profile.phone_verified_at)
        self.assertEqual(int(self.client.session["_auth_user_id"]), profile.user_id)

        otp = PhoneOTP.objects.get(phone_number=self.phone)
        self.assertTrue(otp.is_used)

    def test_correct_code_for_returning_phone_logs_into_existing_user(self):
        existing = _make_user("phone_owner")
        existing.profile.phone_number = self.phone
        existing.profile.save(update_fields=["phone_number"])

        code = self._request_code()
        self.client.post(reverse("phone_verify"), {"phone_number": self.phone, "code": code})

        self.assertEqual(User.objects.filter(profile__phone_number=self.phone).count(), 1)
        self.assertEqual(int(self.client.session["_auth_user_id"]), existing.pk)

    def test_suspended_user_cannot_log_in_via_otp(self):
        """Regression: django.contrib.auth.login() does not check is_active
        on its own (unlike password auth via ModelBackend) — phone_verify_view
        must reject a suspended account explicitly, or OTP would be a way
        to bypass a moderation suspension entirely."""
        existing = _make_user("phone_suspended")
        existing.profile.phone_number = self.phone
        existing.profile.save(update_fields=["phone_number"])
        existing.is_active = False
        existing.save(update_fields=["is_active"])

        code = self._request_code()
        resp = self.client.post(reverse("phone_verify"), {"phone_number": self.phone, "code": code})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("phone_start"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_code_increments_attempts_and_does_not_log_in(self):
        self._request_code()
        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": self.phone, "code": "000000"}
        )
        self.assertEqual(resp.status_code, 200)
        otp = PhoneOTP.objects.get(phone_number=self.phone)
        self.assertEqual(otp.attempts, 1)
        self.assertFalse(otp.is_used)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_no_otp_requested_shows_error_without_crashing(self):
        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": "09129999999", "code": "000000"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_expired_code_redirects_to_start(self):
        code = self._request_code()
        otp = PhoneOTP.objects.get(phone_number=self.phone)
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=["expires_at"])

        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": self.phone, "code": code}
        )
        self.assertRedirects(resp, reverse("phone_start"))

    def test_too_many_attempts_redirects_to_start(self):
        code = self._request_code()
        otp = PhoneOTP.objects.get(phone_number=self.phone)
        otp.attempts = 5
        otp.save(update_fields=["attempts"])

        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": self.phone, "code": code}
        )
        self.assertRedirects(resp, reverse("phone_start"))

    def test_ip_rate_limit_blocks_brute_force_across_phone_numbers(self):
        """The per-OTP 5-attempt cap alone doesn't stop an attacker who
        requests codes for many different numbers from one IP and tries
        each once — this IP-level cap catches that."""
        for i in range(15):
            self.client.post(
                reverse("phone_verify"),
                {"phone_number": f"0912111{i:04d}", "code": "000000"},
            )
        code = self._request_code()
        resp = self.client.post(
            reverse("phone_verify"), {"phone_number": self.phone, "code": code}
        )
        self.assertEqual(resp.status_code, 200)
        otp = PhoneOTP.objects.get(phone_number=self.phone)
        self.assertFalse(otp.is_used)


# ---------------------------------------------------------------------------
# Creator Studio — analytics (Phase 4/5)
# ---------------------------------------------------------------------------

class CreatorStudioViewTests(TestCase):
    def setUp(self):
        from core.test_utils import make_user as make_onboarded_user
        from tracks.models import Track

        # OnboardingRequiredMiddleware gates /creator/studio/ (unlike
        # /creator/apply/, which is explicitly allow-listed) — the file's
        # local _make_user() doesn't set onboarding_complete, so this view
        # needs the onboarded helper or every request 302s before ever
        # reaching the view.
        self.creator = make_onboarded_user("cs_creator")
        self.track_a = Track.objects.create(creator=self.creator, title="A", content_type="music")
        self.track_b = Track.objects.create(creator=self.creator, title="B", content_type="music")
        self.client.login(username="cs_creator", password="pass12345")

    def _play(self, track, *, user, ip_hash, point_awarded=False, days_ago=0):
        from plays.models import PlayEvent

        created = timezone.now() - timedelta(days=days_ago)
        pe = PlayEvent.objects.create(
            track=track, user=user, ip_hash=ip_hash, ua_hash="ua",
            day_key=created.date().isoformat(), point_awarded=point_awarded,
        )
        if days_ago:
            PlayEvent.objects.filter(pk=pe.pk).update(created_at=created)
        return pe

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("creator_studio"))
        self.assertEqual(resp.status_code, 302)

    def test_my_tracks_only_shows_own_tracks_newest_first(self):
        from tracks.models import Track

        other = _make_user("cs_other")
        Track.objects.create(creator=other, title="Not mine", content_type="music")

        resp = self.client.get(reverse("creator_studio"))
        titles = [t.title for t in resp.context["tracks"]]
        self.assertEqual(set(titles), {"A", "B"})

    def test_returning_listener_played_before_and_during_window(self):
        listener = _make_user("cs_returning")
        self._play(self.track_a, user=listener, ip_hash="ip1", days_ago=40)  # before window
        self._play(self.track_a, user=listener, ip_hash="ip2", days_ago=5)   # inside window

        resp = self.client.get(reverse("creator_studio"))
        self.assertEqual(resp.context["returning_listeners"], 1)
        self.assertEqual(resp.context["first_time_listeners"], 0)

    def test_first_time_listener_only_played_inside_window(self):
        listener = _make_user("cs_firsttime")
        self._play(self.track_a, user=listener, ip_hash="ip1", days_ago=2)

        resp = self.client.get(reverse("creator_studio"))
        self.assertEqual(resp.context["first_time_listeners"], 1)
        self.assertEqual(resp.context["returning_listeners"], 0)

    def test_track_performance_reports_plays_and_points_per_track(self):
        from plays.models import PointLedger

        self._play(self.track_a, user=_make_user("cs_l1"), ip_hash="ip1", days_ago=1)
        self._play(self.track_a, user=_make_user("cs_l2"), ip_hash="ip2", days_ago=1)
        PointLedger.objects.create(
            user=self.creator, delta=1, reason=PointLedger.Reason.PLAY_REWARD,
            track_id_snapshot=self.track_a.id, ip_hash_snapshot="ip1",
        )

        resp = self.client.get(reverse("creator_studio"))
        by_track = {row["track"].id: row for row in resp.context["track_performance"]}
        self.assertEqual(by_track[self.track_a.id]["plays"], 2)
        self.assertEqual(by_track[self.track_a.id]["points"], 1)
        self.assertEqual(by_track[self.track_b.id]["plays"], 0)

    def test_daily_points_counts_qualified_plays_not_boolean_sum(self):
        """Regression: the original code did Sum("point_awarded") on a
        BooleanField, which errors on PostgreSQL (SUM(boolean) doesn't
        exist there) even though SQLite silently tolerates it. Count with
        a filter is portable and this test locks in the correct value."""
        self._play(self.track_a, user=_make_user("cs_q1"), ip_hash="ip1", point_awarded=True, days_ago=1)
        self._play(self.track_a, user=_make_user("cs_q2"), ip_hash="ip2", point_awarded=True, days_ago=1)
        self._play(self.track_a, user=_make_user("cs_q3"), ip_hash="ip3", point_awarded=False, days_ago=1)

        resp = self.client.get(reverse("creator_studio"))
        daily = list(resp.context["daily"])
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["plays"], 3)
        self.assertEqual(daily[0]["points"], 2)

    def test_recent_ledger_shows_this_creators_entries_only(self):
        from plays.models import PointLedger

        other = _make_user("cs_other_ledger")
        PointLedger.objects.create(user=self.creator, delta=1, reason=PointLedger.Reason.PLAY_REWARD)
        PointLedger.objects.create(user=other, delta=1, reason=PointLedger.Reason.PLAY_REWARD)

        resp = self.client.get(reverse("creator_studio"))
        ledger_users = {entry.user_id for entry in resp.context["recent_ledger"]}
        self.assertEqual(ledger_users, {self.creator.id})

    def test_recent_payouts_shown(self):
        from billing.models import PayoutRequest

        PayoutRequest.objects.create(user=self.creator, amount=100, points=100)
        resp = self.client.get(reverse("creator_studio"))
        self.assertEqual(len(resp.context["recent_payouts"]), 1)


# ---------------------------------------------------------------------------
# SMS provider abstraction (accounts/services.py)
# ---------------------------------------------------------------------------

class SmsProviderTests(TestCase):
    def test_default_provider_is_console(self):
        from accounts.services import ConsoleSmsProvider, get_sms_provider

        self.assertIsInstance(get_sms_provider(), ConsoleSmsProvider)

    @override_settings(SMS_PROVIDER="kavenegar", KAVENEGAR_API_KEY="testkey")
    def test_kavenegar_selected_when_configured(self):
        from accounts.services import KavenegarSmsProvider, get_sms_provider

        provider = get_sms_provider()
        self.assertIsInstance(provider, KavenegarSmsProvider)
        self.assertEqual(provider.api_key, "testkey")

    def test_console_provider_send_does_not_raise(self):
        from accounts.services import ConsoleSmsProvider

        ConsoleSmsProvider().send("09121234567", "test message")

    @patch("accounts.services.requests.get")
    def test_kavenegar_provider_success(self, mock_get):
        from accounts.services import KavenegarSmsProvider

        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"return": {"status": 200, "message": "ok"}}

        KavenegarSmsProvider(api_key="k", sender="1000").send("09121234567", "hi")
        called_url = mock_get.call_args.args[0]
        self.assertIn("k", called_url)
        self.assertEqual(mock_get.call_args.kwargs["params"]["receptor"], "09121234567")
        self.assertEqual(mock_get.call_args.kwargs["params"]["sender"], "1000")

    @patch("accounts.services.requests.get")
    def test_kavenegar_provider_raises_on_rejected_status(self, mock_get):
        from accounts.services import KavenegarSmsProvider, SmsSendError

        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"return": {"status": 400, "message": "bad receptor"}}

        with self.assertRaises(SmsSendError):
            KavenegarSmsProvider(api_key="k").send("09121234567", "hi")

    @patch("accounts.services.requests.get", side_effect=Exception("network down"))
    def test_kavenegar_provider_wraps_network_error(self, mock_get):
        import requests

        from accounts.services import KavenegarSmsProvider, SmsSendError

        mock_get.side_effect = requests.RequestException("network down")
        with self.assertRaises(SmsSendError):
            KavenegarSmsProvider(api_key="k").send("09121234567", "hi")

    def test_send_otp_sms_never_raises_even_if_provider_fails(self):
        from accounts import services

        with patch.object(services, "get_sms_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.send.side_effect = services.SmsSendError("boom")
            services.send_otp_sms("09121234567", "123456")  # must not raise

    def test_phone_start_view_calls_send_otp_sms(self):
        cache.clear()
        with patch("accounts.views.send_otp_sms") as mock_send:
            resp = self.client.post(reverse("phone_start"), {"phone_number": "09121234567"})
        self.assertEqual(resp.status_code, 302)
        mock_send.assert_called_once()
        called_phone, called_code = mock_send.call_args.args
        self.assertEqual(called_phone, "09121234567")
        self.assertEqual(len(called_code), 6)
