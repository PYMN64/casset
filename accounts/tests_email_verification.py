"""accounts/tests_email_verification.py — S10 item 1: e-mail verification
gate for password sign-up.

Google sign-in already proves the address (accounts/oauth.py refuses an
unverified Google email); phone OTP doesn't use email at all. Only the
plain username/password sign-up path needed this gate, so these tests
focus entirely on that path: an account must stay unusable for login
until its verification link is redeemed.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerification, UserProfile
from .services import (
    find_unverified_user_by_email,
    issue_email_verification,
    seconds_until_email_resend,
    verify_email_token,
)

User = get_user_model()

REGISTER_DATA = {
    "username": "newcreator1",
    "email": "newcreator1@example.com",
    "password1": "a-strong-passw0rd!",
    "password2": "a-strong-passw0rd!",
    "accept_terms": "1",
}


class RegisterCreatesInactiveAccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_does_not_log_in_and_sends_verification_email(self):
        response = self.client.post(reverse("register"), REGISTER_DATA, follow=True)

        user = User.objects.get(username="newcreator1")
        self.assertFalse(user.is_active)
        self.assertFalse(user.profile.email_verified)
        self.assertEqual(user.profile.auth_provider, UserProfile.AuthProvider.PASSWORD)

        # Not logged in — the response must render the "check your inbox"
        # page, not redirect into onboarding like the old flow did.
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "newcreator1@example.com")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newcreator1@example.com", mail.outbox[0].to)
        self.assertEqual(EmailVerification.objects.filter(user=user).count(), 1)

    def test_unverified_account_cannot_log_in(self):
        self.client.post(reverse("register"), REGISTER_DATA)
        user = User.objects.get(username="newcreator1")

        response = self.client.post(
            reverse("login"),
            {"username": "newcreator1", "password": "a-strong-passw0rd!"},
        )

        self.assertEqual(response.status_code, 200)  # form_invalid, no redirect
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "ایمیل شما هنوز تایید نشده است")
        self.assertContains(response, reverse("resend_verification_email"))
        self.assertFalse(User.objects.get(pk=user.pk).is_active)


class VerifyEmailTokenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="pendinguser", email="pending@example.com", password="pass12345",
        )
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.profile = self.user.profile
        self.profile.auth_provider = UserProfile.AuthProvider.PASSWORD
        self.profile.save(update_fields=["auth_provider"])

    def _issue(self):
        factory_request = self.client.get("/").wsgi_request
        return issue_email_verification(self.user, factory_request)

    def test_valid_token_activates_and_logs_in(self):
        token = self._issue()
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.get(
            reverse("verify_email", kwargs={"uidb64": uid, "token": token}), follow=True,
        )

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.profile.email_verified)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_wrong_token_is_rejected(self):
        self._issue()
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        ok, user, err = verify_email_token(uid, "not-the-real-token")

        self.assertFalse(ok)
        self.assertIsNone(user)
        self.assertEqual(err, "bad_link")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_token_is_rejected(self):
        token = self._issue()
        EmailVerification.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timezone.timedelta(seconds=1)
        )
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        ok, user, err = verify_email_token(uid, token)

        self.assertFalse(ok)
        self.assertEqual(err, "expired")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_malformed_uid_is_rejected(self):
        ok, user, err = verify_email_token("not-base64-!!", "whatever")
        self.assertFalse(ok)
        self.assertEqual(err, "bad_link")

    def test_already_verified_link_is_idempotent(self):
        """Clicking an already-redeemed link again (e.g. a second click on
        the same e-mail) should not error for an account that ended up
        verified — only a link that never worked is a real error."""
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        token = self._issue()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        ok, _, _ = verify_email_token(uid, token)
        self.assertTrue(ok)

        ok2, user2, err2 = verify_email_token(uid, token)
        self.assertTrue(ok2)
        self.assertEqual(user2.pk, self.user.pk)


class ResendVerificationEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="resenduser", email="resend@example.com", password="pass12345",
        )
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.profile = self.user.profile
        self.profile.auth_provider = UserProfile.AuthProvider.PASSWORD
        self.profile.save(update_fields=["auth_provider"])

    def test_resend_sends_new_email_for_unverified_account(self):
        response = self.client.post(
            reverse("resend_verification_email"), {"email": "resend@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اگر حسابی")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailVerification.objects.filter(user=self.user).count(), 1)

    def test_resend_gives_same_message_for_unknown_email(self):
        """No user-enumeration oracle: an unregistered address gets the
        exact same response as a real, unverified one."""
        response = self.client.post(
            reverse("resend_verification_email"), {"email": "nobody@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اگر حسابی")
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_gives_same_message_for_already_verified_account(self):
        self.profile.email_verified_at = timezone.now()
        self.profile.save(update_fields=["email_verified_at"])
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("resend_verification_email"), {"email": "resend@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اگر حسابی")
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_is_rate_limited_by_cooldown(self):
        request = self.client.get("/").wsgi_request
        issue_email_verification(self.user, request)
        self.assertGreater(seconds_until_email_resend(self.user), 0)

        response = self.client.post(
            reverse("resend_verification_email"), {"email": "resend@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        # Cooldown blocks a second send within the window — only the first
        # (issue_email_verification call above) email went out.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailVerification.objects.filter(user=self.user).count(), 1)

    def test_resend_endpoint_is_ip_rate_limited(self):
        for _ in range(5):
            self.client.post(
                reverse("resend_verification_email"), {"email": "resend@example.com"},
            )
        mail.outbox.clear()

        response = self.client.post(
            reverse("resend_verification_email"), {"email": "resend@example.com"},
        )
        self.assertContains(response, "درخواست‌های زیادی")
        self.assertEqual(len(mail.outbox), 0)


class FindUnverifiedUserByEmailTests(TestCase):
    def test_returns_none_for_google_account(self):
        user = User.objects.create_user(username="googley", email="g@example.com")
        user.is_active = False
        user.save(update_fields=["is_active"])
        user.profile.auth_provider = UserProfile.AuthProvider.GOOGLE
        user.profile.save(update_fields=["auth_provider"])

        self.assertIsNone(find_unverified_user_by_email("g@example.com"))

    def test_returns_none_for_active_account(self):
        User.objects.create_user(username="active1", email="active1@example.com")
        self.assertIsNone(find_unverified_user_by_email("active1@example.com"))
