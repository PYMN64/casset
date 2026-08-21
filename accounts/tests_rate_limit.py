"""accounts/tests_rate_limit.py — S10 item 2: brute-force protection on the
login and registration forms.

Follows the same cache-counter pattern already used for phone OTP
(accounts/tests.py::PhoneStartViewTests) — CassetLoginView.post gates two
independent buckets (IP-wide, and per-account counted on failures only) so
neither a distributed username-spray from one IP nor a targeted password
guess against one account from many IPs gets through.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.test_utils import make_user

User = get_user_model()


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("bruteforceme", password="correct-horse-battery")

    def tearDown(self):
        cache.clear()

    def _attempt(self, *, username="bruteforceme", password="wrong-password"):
        return self.client.post(
            reverse("login"), {"username": username, "password": password},
        )

    def test_account_rate_limit_blocks_after_failed_attempts(self):
        """5 wrong passwords in a row for the same account block the 6th,
        even though the IP-wide cap (20) is nowhere near reached."""
        for _ in range(5):
            resp = self._attempt()
            self.assertEqual(resp.status_code, 200)

        blocked = self._attempt()
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "تلاش‌های ورود ناموفق زیادی", status_code=429)
        self.assertFalse(blocked.wsgi_request.user.is_authenticated)

    def test_account_block_does_not_reach_auth_backend_with_correct_password(self):
        """Once blocked, even the *correct* password is refused — the point
        is that a blocked account can't be distinguished from one under
        attack by trying the real password."""
        for _ in range(5):
            self._attempt()

        resp = self._attempt(password="correct-horse-battery")
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_successful_login_does_not_count_against_account_limit(self):
        """A real user who mistypes a couple of times and then succeeds
        must not be one bad guess away from locking themselves out."""
        for _ in range(4):
            self._attempt()

        ok = self._attempt(password="correct-horse-battery")
        self.assertEqual(ok.status_code, 302)
        self.assertTrue(ok.wsgi_request.user.is_authenticated)

    def test_ip_rate_limit_blocks_brute_force_across_different_accounts(self):
        """An attacker spraying different usernames from one IP must be
        blocked by the IP-wide cap even though no single account hit its
        own (lower) per-account threshold."""
        for i in range(20):
            self._attempt(username=f"nosuchuser{i}", password="whatever")

        blocked = self._attempt(username="yet-another-user", password="whatever")
        self.assertEqual(blocked.status_code, 429)

    def test_rate_limited_response_shows_friendly_message_not_bare_429(self):
        for _ in range(5):
            self._attempt()

        resp = self._attempt()
        self.assertEqual(resp.status_code, 429)
        # Rendered through the normal login template (with messages), not a
        # bare/default error page.
        self.assertTemplateUsed(resp, "accounts/login.html")
        self.assertContains(resp, "تلاش‌های ورود ناموفق زیادی", status_code=429)


class RegisterRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _submit(self, i):
        return self.client.post(reverse("register"), {
            "username": f"ratelimituser{i}",
            "password1": "V3ryStr0ngPass!",
            "password2": "V3ryStr0ngPass!",
            "email": f"ratelimituser{i}@example.com",
            "accept_terms": "on",
        })

    def test_ip_rate_limit_blocks_repeated_registration_attempts(self):
        for i in range(10):
            resp = self._submit(i)
            self.assertEqual(resp.status_code, 200)

        blocked = self._submit(999)
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "درخواست‌های زیادی", status_code=429)
        self.assertFalse(User.objects.filter(username="ratelimituser999").exists())
