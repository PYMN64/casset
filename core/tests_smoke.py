"""core/tests_smoke.py — Smoke tests for every public page in Casset.

Purpose
-------
A "smoke test" doesn't check business logic. It only asks:
    "Does this page load without crashing?"

This catches:
  * TemplateDoesNotExist
  * NoReverseMatch (broken {% url %} tags)
  * AttributeError on missing model fields
  * 500 errors from bad querysets

Run with:
    python manage.py test core.tests_smoke --verbosity=2

Reading the output
------------------
  ok   → page loads (200 / 302 / 404 as expected)
  FAIL → wrong status code
  ERROR→ the view crashed (this is the important one)
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import PlatformSetting
from core.test_utils import make_superuser, make_user
from tracks.models import Track

User = get_user_model()


def _make_user(username="smoke_user", onboarded=True):
    return make_user(username, onboarded=onboarded)


def _make_track(creator, title="Smoke Track"):
    return Track.objects.create(
        creator=creator,
        title=title,
        content_type="music",
        duration_seconds=180,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    )


# ---------------------------------------------------------------------------
# 1. Anonymous pages — must load for logged-out visitors
# ---------------------------------------------------------------------------

class AnonymousPagesTests(TestCase):
    """Pages a visitor can see without logging in."""

    def setUp(self):
        PlatformSetting.get_solo()

    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_discover(self):
        self.assertEqual(self.client.get("/discover/").status_code, 200)

    def test_search_empty(self):
        self.assertEqual(self.client.get("/search/").status_code, 200)

    def test_search_with_query(self):
        self.assertEqual(self.client.get("/search/?q=test").status_code, 200)

    def test_trending(self):
        self.assertEqual(self.client.get("/trending/").status_code, 200)

    def test_track_list(self):
        self.assertEqual(self.client.get("/tracks/").status_code, 200)

    def test_login_page(self):
        self.assertEqual(self.client.get("/login/").status_code, 200)

    def test_register_page(self):
        self.assertEqual(self.client.get("/register/").status_code, 200)

    def test_phone_start(self):
        self.assertEqual(self.client.get("/phone/").status_code, 200)

    def test_api_search(self):
        self.assertEqual(self.client.get("/api/v1/search/?q=a").status_code, 200)


# ---------------------------------------------------------------------------
# 2. Auth-required pages — must redirect (302) when logged out
# ---------------------------------------------------------------------------

class AuthRedirectTests(TestCase):
    """Every protected page must redirect anonymous visitors, not crash."""

    PROTECTED_URLS = [
        "/dashboard/",
        "/settings/",
        "/upload/",
        "/my/tracks/",
        "/albums/",
        "/albums/create/",
        "/library/",
        "/notifications/",
        "/creator/apply/",
        "/creator/studio/",
        "/onboarding/",
    ]

    def test_all_protected_pages_redirect(self):
        for url in self.PROTECTED_URLS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(
                    resp.status_code, 302,
                    f"{url} should redirect anonymous users, got {resp.status_code}",
                )


# ---------------------------------------------------------------------------
# 3. Logged-in pages — must render (200) for an authenticated user
# ---------------------------------------------------------------------------

class LoggedInPagesTests(TestCase):
    """Every page a logged-in, onboarded user can reach."""

    def setUp(self):
        PlatformSetting.get_solo()
        self.user = _make_user("smoke_logged_in")
        self.track = _make_track(self.user)
        self.client.login(username="smoke_logged_in", password="pass12345")

    def test_dashboard(self):
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_settings(self):
        self.assertEqual(self.client.get("/settings/").status_code, 200)

    def test_upload_page(self):
        self.assertEqual(self.client.get("/upload/").status_code, 200)

    def test_my_tracks(self):
        self.assertEqual(self.client.get("/my/tracks/").status_code, 200)

    def test_album_list(self):
        self.assertEqual(self.client.get("/albums/").status_code, 200)

    def test_album_create(self):
        self.assertEqual(self.client.get("/albums/create/").status_code, 200)

    def test_library(self):
        self.assertEqual(self.client.get("/library/").status_code, 200)

    def test_notifications(self):
        self.assertEqual(self.client.get("/notifications/").status_code, 200)

    def test_notifications_api(self):
        self.assertEqual(self.client.get("/api/v1/notifications/").status_code, 200)

    def test_creator_apply(self):
        self.assertEqual(self.client.get("/creator/apply/").status_code, 200)

    def test_creator_studio(self):
        self.assertEqual(self.client.get("/creator/studio/").status_code, 200)

    def test_own_public_profile(self):
        resp = self.client.get(f"/@{self.user.username}/")
        self.assertEqual(resp.status_code, 200)

    def test_track_detail(self):
        resp = self.client.get(f"/t/{self.track.slug}/")
        self.assertEqual(resp.status_code, 200)

    def test_edit_track(self):
        resp = self.client.get(f"/my/tracks/{self.track.id}/edit/")
        self.assertEqual(resp.status_code, 200)

    def test_playlist_mine_api(self):
        self.assertEqual(
            self.client.get("/api/v1/playlist/mine/").status_code, 200
        )


# ---------------------------------------------------------------------------
# 4. 404 handling — bad IDs must 404, not 500
# ---------------------------------------------------------------------------

class NotFoundTests(TestCase):
    """Nonexistent resources must return 404, never crash with 500."""

    def setUp(self):
        PlatformSetting.get_solo()
        self.user = _make_user("smoke_404")
        self.client.login(username="smoke_404", password="pass12345")

    def test_unknown_track_slug(self):
        self.assertEqual(self.client.get("/t/does-not-exist/").status_code, 404)

    def test_unknown_username(self):
        self.assertEqual(self.client.get("/@nobody12345/").status_code, 404)

    def test_unknown_album(self):
        self.assertEqual(self.client.get("/albums/999999/edit/").status_code, 404)

    def test_unknown_playlist(self):
        self.assertEqual(self.client.get("/p/999999/").status_code, 404)


# ---------------------------------------------------------------------------
# 5. Onboarding gate — incomplete users get pushed to onboarding
# ---------------------------------------------------------------------------

class OnboardingGateTests(TestCase):
    """A user who hasn't finished onboarding gets redirected there."""

    def setUp(self):
        PlatformSetting.get_solo()
        self.user = _make_user("smoke_onboard", onboarded=False)
        self.client.login(username="smoke_onboard", password="pass12345")

    def test_redirected_to_onboarding(self):
        resp = self.client.get("/tracks/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("onboarding", resp["Location"])

    def test_onboarding_page_itself_loads(self):
        self.assertEqual(self.client.get("/onboarding/").status_code, 200)


# ---------------------------------------------------------------------------
# 6. Admin — every registered model's changelist must load
# ---------------------------------------------------------------------------

class AdminSmokeTests(TestCase):
    """Catches broken list_display / list_filter / fieldsets in admin.py."""

    ADMIN_URLS = [
        "/admin/accounts/userprofile/",
        "/admin/tracks/track/",
        "/admin/tracks/album/",
        "/admin/tracks/genre/",
        "/admin/plays/playevent/",
        "/admin/plays/pointledger/",
        "/admin/plays/fraudflag/",
        "/admin/notifications/notification/",
        "/admin/billing/plan/",
        "/admin/billing/invoice/",
        "/admin/interactions/comment/",
        "/admin/interactions/trackfavorite/",
        "/admin/moderation/report/",
    ]

    def setUp(self):
        self.admin = make_superuser("smoke_admin")
        self.client.login(username="smoke_admin", password="pass12345")

    def test_admin_index(self):
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_all_admin_changelists(self):
        for url in self.ADMIN_URLS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(
                    resp.status_code, 200,
                    f"Admin page {url} failed with {resp.status_code}",
                )


# ---------------------------------------------------------------------------
# 6. Template hygiene
# ---------------------------------------------------------------------------

class TemplateCommentHygieneTests(TestCase):
    """Django's {# #} comment is SINGLE-LINE only.

    Spanning it across lines does not comment anything out — the opening
    line disappears and every following line is rendered as visible text
    on the page. That shipped once already; this makes it impossible to
    ship again without the suite going red.
    """

    def test_no_multiline_hash_comments_in_any_template(self):
        from pathlib import Path

        from django.conf import settings

        offenders = []
        for template_dir in settings.TEMPLATES[0]["DIRS"]:
            for path in Path(template_dir).rglob("*.html"):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if "{#" in line and "#}" not in line:
                        offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders, [],
            "Use {% comment %}…{% endcomment %} for multi-line comments; "
            f"these {{# … leak into the rendered page: {offenders}",
        )

    def test_rendered_pages_contain_no_template_comment_markers(self):
        """Belt and braces: assert on the actual output, not just source."""
        PlatformSetting.get_solo()
        _make_user("hygiene_user")
        self.client.login(username="hygiene_user", password="pass12345")
        for url in ("/discover/", "/library/", "/settings/", "/dashboard/", "/upload/", "/login/"):
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                self.assertNotIn("{#", body)
                self.assertNotIn("{%", body)
