"""core/tests.py — health check, backup command, and the staff console.

The staff console (users_console/creators_console/creator_detail) had zero
tests before this file — worse, core/staff_urls.py was never include()'d in
config/urls.py at all, so every one of these views was unreachable at any
URL in the running app. Both gaps are closed here: config/urls.py now
mounts core.staff_urls under staff/, and these tests exercise it for real
through the URL layer (reverse("staff:...")), not just by calling the view
function directly, so a routing regression like that can't hide again.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from core.test_utils import make_superuser, make_user
from tracks.models import Track

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthCheckTests(TestCase):
    def test_healthy_returns_200(self):
        resp = self.client.get(reverse("health_check"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertEqual(data["checks"]["cache"], "ok")

    def test_no_login_required(self):
        # Load balancers/uptime monitors never authenticate.
        resp = self.client.get(reverse("health_check"))
        self.assertNotEqual(resp.status_code, 302)

    @patch("core.views.connection")
    def test_database_failure_returns_503(self, mock_connection):
        mock_connection.cursor.side_effect = Exception("connection refused")
        resp = self.client.get(reverse("health_check"))
        self.assertEqual(resp.status_code, 503)
        data = resp.json()
        self.assertEqual(data["status"], "degraded")
        self.assertIn("error", data["checks"]["database"])


# ---------------------------------------------------------------------------
# backup_db management command
# ---------------------------------------------------------------------------

class BackupDbCommandTests(TestCase):
    @patch("core.management.commands.backup_db.settings")
    def test_refuses_on_sqlite(self, mock_settings):
        # Mocked explicitly (not relying on the ambient test DB engine)
        # because this test is also exercised by the live-Postgres
        # verification pass (.casset/state/changelog.md) — against a real
        # postgresql connection it would otherwise skip straight past the
        # "wrong engine" guard and shell out to a real pg_dump instead.
        mock_settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
        with self.assertRaises(CommandError):
            call_command("backup_db")

    @patch("core.management.commands.backup_db.settings")
    @patch("core.management.commands.backup_db.subprocess.run")
    def test_invokes_pg_dump_with_expected_args(self, mock_run, mock_settings):
        import tempfile

        def _fake_pg_dump(cmd, **kwargs):
            file_arg = next(a for a in cmd if a.startswith("--file="))
            with open(file_arg.split("=", 1)[1], "wb") as f:
                f.write(b"x" * 100)

        mock_run.side_effect = _fake_pg_dump
        mock_settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "casset", "USER": "casset_user", "PASSWORD": "secret",
                "HOST": "dbhost", "PORT": "5432",
            }
        }
        with tempfile.TemporaryDirectory() as out_dir:
            call_command("backup_db", output_dir=out_dir)

        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], "pg_dump")
        self.assertIn("--username=casset_user", args)
        self.assertIn("casset", args)
        self.assertEqual(mock_run.call_args.kwargs["env"]["PGPASSWORD"], "secret")

    @patch("core.management.commands.backup_db.settings")
    @patch("core.management.commands.backup_db.subprocess.run", side_effect=FileNotFoundError())
    def test_missing_pg_dump_binary_raises_clear_error(self, mock_run, mock_settings):
        import tempfile

        mock_settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "casset", "USER": "u", "PASSWORD": "p", "HOST": "h", "PORT": "5432",
            }
        }
        with tempfile.TemporaryDirectory() as out_dir, self.assertRaises(CommandError):
            call_command("backup_db", output_dir=out_dir)


# ---------------------------------------------------------------------------
# Staff console — access control
# ---------------------------------------------------------------------------

class StaffConsoleAccessTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_console_admin")
        self.regular = make_user("staff_console_regular")

    def test_users_console_requires_staff(self):
        self.client.login(username="staff_console_regular", password="pass12345")
        resp = self.client.get(reverse("staff:users_console"))
        self.assertNotEqual(resp.status_code, 200)

    def test_users_console_anonymous_redirected(self):
        resp = self.client.get(reverse("staff:users_console"))
        self.assertEqual(resp.status_code, 302)

    def test_users_console_staff_ok(self):
        self.client.login(username="staff_console_admin", password="pass12345")
        resp = self.client.get(reverse("staff:users_console"))
        self.assertEqual(resp.status_code, 200)

    def test_creators_console_staff_ok(self):
        self.client.login(username="staff_console_admin", password="pass12345")
        resp = self.client.get(reverse("staff:creators_console"))
        self.assertEqual(resp.status_code, 200)

    def test_creator_detail_staff_ok(self):
        self.client.login(username="staff_console_admin", password="pass12345")
        resp = self.client.get(reverse("staff:creator_detail", args=[self.regular.id]))
        self.assertEqual(resp.status_code, 200)

    def test_creator_detail_unknown_user_404(self):
        self.client.login(username="staff_console_admin", password="pass12345")
        resp = self.client.get(reverse("staff:creator_detail", args=[999999]))
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Staff console — content correctness
# ---------------------------------------------------------------------------

class StaffConsoleContentTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_console_admin2")
        self.creator = make_user("staff_console_creator")
        self.client.login(username="staff_console_admin2", password="pass12345")

    def test_users_console_search_filters_by_username(self):
        make_user("findable_zzz")
        resp = self.client.get(reverse("staff:users_console"), {"q": "findable_zzz"})
        usernames = [p.user.username for p in resp.context["profiles"]]
        self.assertEqual(usernames, ["findable_zzz"])

    def test_users_console_points_earned_annotation_correct(self):
        """Regression: points_earned used Sum(BooleanField), which errors on
        PostgreSQL (SUM(boolean) doesn't exist there) even though SQLite
        silently tolerates it — caught by a live-Postgres verification run
        after this session mounted core.staff_urls for the first time (it
        was previously unreachable, so the bug had never actually fired)."""
        from plays.models import PlayEvent

        track = Track.objects.create(creator=self.creator, title="T2", content_type="music")
        PlayEvent.objects.create(track=track, user=None, ip_hash="ip1", day_key="2026-01-01", point_awarded=True)
        PlayEvent.objects.create(track=track, user=None, ip_hash="ip2", day_key="2026-01-01", point_awarded=False)

        resp = self.client.get(reverse("staff:users_console"))
        row = next(p for p in resp.context["profiles"] if p.user_id == self.creator.id)
        self.assertEqual(row.points_earned, 1)

    def test_creators_console_filters_by_status(self):
        self.creator.profile.creator_status = "approved"
        self.creator.profile.save(update_fields=["creator_status"])
        resp = self.client.get(reverse("staff:creators_console"), {"status": "approved"})
        ids = [p.user_id for p in resp.context["profiles"]]
        self.assertIn(self.creator.id, ids)

    def test_platform_dashboard_requires_staff(self):
        make_user("dash_regular")
        self.client.login(username="dash_regular", password="pass12345")
        resp = self.client.get(reverse("staff:platform_dashboard"))
        self.assertNotEqual(resp.status_code, 200)

    def test_platform_dashboard_staff_ok(self):
        resp = self.client.get(reverse("staff:platform_dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_platform_dashboard_revenue_and_points(self):
        from billing.models import Invoice, Plan
        from plays.models import PointLedger

        plan = Plan.objects.create(code="p1", title="P1", price=1000)
        inv = Invoice.objects.create(user=self.creator, plan=plan, amount=1000)
        inv.mark_paid()
        PointLedger.objects.create(user=self.creator, delta=5, reason=PointLedger.Reason.PLAY_REWARD)
        PointLedger.objects.create(user=self.creator, delta=-2, reason=PointLedger.Reason.PAYOUT_DEDUCTION)

        resp = self.client.get(reverse("staff:platform_dashboard"))
        self.assertEqual(resp.context["revenue_total"], 1000)
        self.assertEqual(resp.context["points_issued"], 5)
        self.assertEqual(resp.context["points_redeemed"], 2)
        self.assertEqual(resp.context["points_outstanding"], 3)

    def test_platform_dashboard_pending_queue_counts(self):
        from billing.models import PayoutRequest
        from moderation.models import Report

        Track.objects.create(creator=self.creator, title="Pending", content_type="music", status=Track.Status.SUBMITTED)
        Report.objects.create(target_type=Report.TargetType.PROFILE, target_user=self.creator, reason=Report.Reason.SPAM)
        PayoutRequest.objects.create(user=self.creator, amount=50, points=50)

        resp = self.client.get(reverse("staff:platform_dashboard"))
        self.assertEqual(resp.context["pending_tracks"], 1)
        self.assertEqual(resp.context["pending_reports"], 1)
        self.assertEqual(resp.context["pending_payout_count"], 1)
        self.assertEqual(resp.context["pending_payout_amount"], 50)

    def test_creator_detail_shows_track_totals(self):
        from plays.models import PlayEvent

        track = Track.objects.create(
            creator=self.creator, title="T", content_type="music",
        )
        PlayEvent.objects.create(
            track=track, user=None, ip_hash="ip1", day_key="2026-01-01", point_awarded=True,
        )
        resp = self.client.get(reverse("staff:creator_detail", args=[self.creator.id]))
        self.assertEqual(resp.context["totals"]["plays"], 1)
        self.assertEqual(resp.context["totals"]["valid_plays"], 1)
