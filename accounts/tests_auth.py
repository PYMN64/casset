"""accounts/tests_auth.py — Google sign-in, publisher eligibility, and the
logged-in phone-verification flow.

Kept separate from accounts/tests.py, which covers the pre-existing
password/OTP/profile surface. These are the behaviours introduced by the
Orange Noir v2 work and each one is a security boundary, not a cosmetic
feature — hence the emphasis on the negative cases.
"""

import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.test_utils import make_publisher, make_user

from . import oauth
from .models import UserProfile
from .services import (
    attach_phone_to_user,
    is_valid_iran_mobile,
    normalize_phone,
    resolve_google_user,
    verify_otp,
)

User = get_user_model()

GOOGLE_SETTINGS = {
    "GOOGLE_OAUTH_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
}


def _id_token(payload: dict) -> str:
    """Build an unsigned JWT with the given claims.

    Signature is irrelevant here for the same reason it is irrelevant in
    production: accounts/oauth.py reads the token out of the body of a
    direct TLS call to Google's token endpoint and validates the claims,
    not the signature. See that module's docstring.
    """
    import base64
    import json

    def seg(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{seg({'alg': 'RS256'})}.{seg(payload)}.signature"


def _claims(**overrides):
    base = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_SETTINGS["GOOGLE_OAUTH_CLIENT_ID"],
        "exp": int(time.time()) + 600,
        "sub": "google-subject-123",
        "email": "person@example.com",
        "email_verified": True,
        "name": "علی رضایی",
    }
    base.update(overrides)
    return base


class _FakeTokenResponse:
    status_code = 200

    def __init__(self, id_token):
        self._id_token = id_token

    def json(self):
        return {"id_token": self._id_token, "access_token": "x"}


# ---------------------------------------------------------------------------
# Phone normalisation
# ---------------------------------------------------------------------------

class PhoneNormalisationTests(TestCase):
    def test_every_common_iranian_format_normalises_to_one_value(self):
        for raw in [
            "09121234567", "+989121234567", "989121234567", "00989121234567",
            "9121234567", "0912 123 4567", "0912-123-4567",
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), "09121234567")

    def test_persian_digits_are_accepted(self):
        """A Farsi keyboard produces ۰۹۱۲…; refusing it would look like the
        form is broken to the majority of our users."""
        self.assertEqual(normalize_phone("۰۹۱۲۱۲۳۴۵۶۷"), "09121234567")
        self.assertTrue(is_valid_iran_mobile("۰۹۱۲۱۲۳۴۵۶۷"))

    def test_obviously_wrong_numbers_are_rejected(self):
        for raw in ["", "123", "08121234567", "091212345678", "abcdefghijk"]:
            with self.subTest(raw=raw):
                self.assertFalse(is_valid_iran_mobile(raw))


# ---------------------------------------------------------------------------
# OTP service
# ---------------------------------------------------------------------------

class OtpServiceTests(TestCase):
    phone = "09121234567"

    def setUp(self):
        cache.clear()

    def test_correct_code_is_burned_so_it_cannot_be_reused(self):
        from .models import PhoneOTP
        from .services import hash_otp_code

        PhoneOTP.objects.create(
            phone_number=self.phone,
            code_hash=hash_otp_code(self.phone, "123456"),
            expires_at=timezone.now() + timezone.timedelta(minutes=2),
            last_sent_at=timezone.now(),
        )
        self.assertEqual(verify_otp(self.phone, "123456"), (True, ""))
        # Second redemption of the same code must fail.
        ok, err = verify_otp(self.phone, "123456")
        self.assertFalse(ok)
        self.assertEqual(err, "not_found")

    def test_persian_digits_in_the_code_are_accepted(self):
        from .models import PhoneOTP
        from .services import hash_otp_code

        PhoneOTP.objects.create(
            phone_number=self.phone,
            code_hash=hash_otp_code(self.phone, "123456"),
            expires_at=timezone.now() + timezone.timedelta(minutes=2),
            last_sent_at=timezone.now(),
        )
        ok, _ = verify_otp(self.phone, "۱۲۳۴۵۶")
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# Google sign-in
# ---------------------------------------------------------------------------

@override_settings(**GOOGLE_SETTINGS)
class GoogleOAuthFlowTests(TestCase):
    def test_start_redirects_to_google_with_pkce_and_state(self):
        resp = self.client.get(reverse("google_login"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith(oauth.AUTH_ENDPOINT))
        for param in ("code_challenge=", "code_challenge_method=S256", "state=", "nonce="):
            self.assertIn(param, resp.url)

    def test_button_hidden_when_not_configured(self):
        """A misconfigured deployment degrades to phone/password sign-in
        rather than showing a button that goes nowhere."""
        with override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET=""):
            resp = self.client.get(reverse("login"))
            self.assertFalse(resp.context["google_enabled"])
            self.assertNotContains(resp, reverse("google_login"))

    def _complete_flow(self, claims=None, tamper_state=None):
        start = self.client.get(reverse("google_login"))
        self.assertEqual(start.status_code, 302)
        flow = self.client.session[oauth.SESSION_KEY]

        payload = _claims(nonce=flow["nonce"])
        if claims:
            payload.update(claims)

        with patch("accounts.oauth.requests.post", return_value=_FakeTokenResponse(_id_token(payload))):
            return self.client.get(reverse("google_callback"), {
                "code": "auth-code",
                "state": tamper_state if tamper_state is not None else flow["state"],
            })

    def test_successful_first_sign_in_creates_account_and_logs_in(self):
        resp = self._complete_flow()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

        profile = UserProfile.objects.get(google_sub="google-subject-123")
        self.assertEqual(profile.user.email, "person@example.com")
        self.assertEqual(profile.auth_provider, UserProfile.AuthProvider.GOOGLE)
        self.assertIsNotNone(profile.email_verified_at)
        # Username must not leak the email address.
        self.assertNotIn("person", profile.user.username)

    def test_state_mismatch_is_rejected(self):
        """Without this check our own callback would accept a login
        initiated by someone else — the classic login-CSRF."""
        resp = self._complete_flow(tamper_state="not-the-real-state")
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 0)

    def test_nonce_mismatch_is_rejected(self):
        self._complete_flow(claims={"nonce": "someone-elses-nonce"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_audience_is_rejected(self):
        """An ID token minted for a different client must not sign anyone in."""
        self._complete_flow(claims={"aud": "another-app.apps.googleusercontent.com"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_issuer_is_rejected(self):
        self._complete_flow(claims={"iss": "https://evil.example"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 0)

    def test_expired_token_is_rejected(self):
        self._complete_flow(claims={"exp": int(time.time()) - 10})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 0)

    def test_unverified_google_email_is_refused(self):
        """This is the account-takeover guard: an unverified address could
        be any address, and match-by-email would then hand over an
        existing Casset account."""
        make_user("victim", email="person@example.com")
        self._complete_flow(claims={"email_verified": False})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_replaying_the_callback_twice_fails_the_second_time(self):
        """The flow is popped from the session on use, so a captured
        callback URL is not replayable."""
        first = self._complete_flow()
        self.assertEqual(first.status_code, 302)
        self.client.logout()
        with patch("accounts.oauth.requests.post",
                   return_value=_FakeTokenResponse(_id_token(_claims(nonce="x")))):
            resp = self.client.get(reverse("google_callback"), {"code": "c", "state": "s"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(resp.status_code, 302)


class GoogleAccountResolutionTests(TestCase):
    def test_matches_existing_account_by_verified_email(self):
        """Signing in with Google using an address that already has a
        Casset account links the two instead of creating a duplicate."""
        existing = make_user("byemail", email="person@example.com")
        user, created = resolve_google_user({
            "sub": "sub-1", "email": "person@example.com", "name": "", "picture": "",
        })
        self.assertFalse(created)
        self.assertEqual(user.pk, existing.pk)
        existing.profile.refresh_from_db()
        self.assertEqual(existing.profile.google_sub, "sub-1")

    def test_subject_wins_over_a_changed_email(self):
        """Google's subject id is immutable; the address is not. Matching
        on the subject first means changing your Gmail address does not
        strand your Casset account."""
        user, _ = resolve_google_user({"sub": "sub-2", "email": "old@example.com", "name": "", "picture": ""})
        again, created = resolve_google_user({"sub": "sub-2", "email": "new@example.com", "name": "", "picture": ""})
        self.assertFalse(created)
        self.assertEqual(again.pk, user.pk)


# ---------------------------------------------------------------------------
# Publisher eligibility
# ---------------------------------------------------------------------------

class PublisherEligibilityTests(TestCase):
    def setUp(self):
        self.user = make_user("eligible_user")
        self.profile = self.user.profile

    def test_new_account_cannot_publish(self):
        self.assertFalse(self.profile.can_publish)
        self.assertEqual(self.profile.publish_blockers(), ["phone", "handle"])

    def test_handle_alone_is_not_enough(self):
        self.profile.public_handle = "someone"
        self.profile.save()
        self.assertFalse(self.profile.can_publish)
        self.assertEqual(self.profile.publish_blockers(), ["phone"])

    def test_phone_alone_is_not_enough(self):
        self.profile.phone_number = "09120001111"
        self.profile.phone_verified_at = timezone.now()
        self.profile.save()
        self.assertFalse(self.profile.can_publish)
        self.assertEqual(self.profile.publish_blockers(), ["handle"])

    def test_both_together_grant_publishing(self):
        publisher = make_publisher("ready_to_publish")
        self.assertTrue(publisher.profile.can_publish)
        self.assertEqual(publisher.profile.publish_blockers(), [])

    def test_rejected_creator_cannot_publish_even_when_complete(self):
        publisher = make_publisher("rejected_creator")
        profile = publisher.profile
        profile.creator_status = UserProfile.CreatorStatus.REJECTED
        profile.save()
        self.assertFalse(profile.can_publish)

    def test_profile_url_prefers_the_handle(self):
        publisher = make_publisher("handle_url", handle="mixtape")
        self.assertEqual(publisher.profile.profile_url, "/mixtape/")

    def test_profile_url_falls_back_to_username(self):
        self.assertEqual(self.profile.profile_url, "/@eligible_user/")


class CreatorHandleFlowTests(TestCase):
    """Choosing a handle is the act that turns a listener into a publisher."""

    def setUp(self):
        cache.clear()
        self.user = make_user("handle_picker")
        self.client.login(username="handle_picker", password="pass12345")

    def test_handle_page_requires_a_verified_phone_first(self):
        resp = self.client.get(reverse("creator_handle"))
        self.assertRedirects(resp, reverse("account_phone_start"))

    def test_choosing_a_handle_enables_publishing(self):
        profile = self.user.profile
        profile.phone_number = "09120002222"
        profile.phone_verified_at = timezone.now()
        profile.save()

        resp = self.client.post(reverse("creator_handle"), {"public_handle": "my_music"})
        self.assertRedirects(resp, reverse("creator_studio"))

        profile.refresh_from_db()
        self.assertEqual(profile.public_handle, "my_music")
        self.assertTrue(profile.creator_enabled)
        self.assertEqual(profile.creator_status, UserProfile.CreatorStatus.APPROVED)
        self.assertTrue(profile.can_publish)

    def test_reserved_handles_are_refused(self):
        profile = self.user.profile
        profile.phone_number = "09120003333"
        profile.phone_verified_at = timezone.now()
        profile.save()

        # "settings" is a real route; allowing it as a handle would shadow it.
        resp = self.client.post(reverse("creator_handle"), {"public_handle": "settings"})
        self.assertEqual(resp.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNone(profile.public_handle)


class PhoneAttachTests(TestCase):
    def test_attaching_a_number_marks_it_verified(self):
        user = make_user("attach_me")
        ok, err = attach_phone_to_user(user, "+989120004444")
        self.assertTrue(ok, err)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.phone_number, "09120004444")
        self.assertTrue(user.profile.phone_verified)

    def test_a_number_already_bound_elsewhere_is_refused(self):
        """Stealing a verified number from another account would be an
        account-takeover path, since the number is a login credential."""
        owner = make_user("phone_owner")
        attach_phone_to_user(owner, "09120005555")

        thief = make_user("phone_thief")
        ok, err = attach_phone_to_user(thief, "09120005555")
        self.assertFalse(ok)
        self.assertEqual(err, "phone_taken")
        thief.profile.refresh_from_db()
        self.assertIsNone(thief.profile.phone_number)


# ---------------------------------------------------------------------------
# Session security
# ---------------------------------------------------------------------------

class SessionSecurityTests(TestCase):
    def setUp(self):
        self.user = make_user("session_user")

    def test_logout_ignores_get(self):
        """A GET logout can be fired by any third-party page embedding an
        <img> pointing at it."""
        self.client.login(username="session_user", password="pass12345")
        resp = self.client.get(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_works_on_post(self):
        self.client.login(username="session_user", password="pass12345")
        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_remember_me_unchecked_expires_with_the_browser(self):
        resp = self.client.post(reverse("login"), {
            "username": "session_user", "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_remember_me_checked_keeps_the_session(self):
        resp = self.client.post(reverse("login"), {
            "username": "session_user", "password": "pass12345", "remember_me": "1",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_next_parameter_cannot_point_off_site(self):
        """Otherwise our own login page becomes a phishing redirector."""
        resp = self.client.get(reverse("login") + "?next=https://evil.example/steal")
        self.assertEqual(resp.context["next"], "")

    def test_next_parameter_keeps_a_local_path(self):
        resp = self.client.get(reverse("login") + "?next=/library/")
        self.assertEqual(resp.context["next"], "/library/")


class AccountDeactivationTests(TestCase):
    def setUp(self):
        self.user = make_publisher("quitter", handle="quitter")
        self.client.login(username="quitter", password="pass12345")

    def test_wrong_confirmation_does_nothing(self):
        resp = self.client.post(reverse("deactivate_account"), {"confirm": "not-my-name"})
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_correct_confirmation_deactivates_and_hides_content(self):
        from tracks.models import Track

        track = Track.objects.create(
            creator=self.user, title="Bye", content_type="music",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )
        resp = self.client.post(reverse("deactivate_account"), {"confirm": "quitter"})
        self.assertEqual(resp.status_code, 302)

        self.user.refresh_from_db()
        track.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(track.visibility, Track.Visibility.PRIVATE)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deactivated_account_cannot_log_back_in(self):
        self.client.post(reverse("deactivate_account"), {"confirm": "quitter"})
        self.client.logout()
        resp = self.client.post(reverse("login"), {
            "username": "quitter", "password": "pass12345",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
