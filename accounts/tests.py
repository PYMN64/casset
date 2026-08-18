"""accounts/tests.py — Tests for authentication, onboarding, and creator flows."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import UserProfile, PhoneOTP

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
        from django.db.models.signals import post_save
        from accounts.models import ensure_profile
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

    def test_404_for_unknown_user(self):
        resp = self.client.get(reverse("public_profile", args=["doesnotexist"]))
        self.assertEqual(resp.status_code, 404)


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


class PhoneVerifyViewTests(TestCase):
    phone = "09121234567"
    fixed_code = "123456"

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
