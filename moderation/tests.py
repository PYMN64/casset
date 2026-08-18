from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from core.test_utils import make_superuser, make_user
from notifications.models import Notification
from tracks.models import Track
from .models import AuditLog, Report


class ModerationReportTests(TestCase):
    def setUp(self):
        # LocMemCache is shared across tests in the same process. The report
        # view rate-limits by IP, so leftover counters from earlier tests make
        # this one fail with 'rate_limited' instead of the duplicate check.
        cache.clear()
        self.reporter = make_user("rep")
        self.creator = make_user("cre")
        self.track = Track.objects.create(creator=self.creator, title="T", slug="t", status=Track.Status.APPROVED)

    def tearDown(self):
        cache.clear()

    def test_report_track_once_per_day(self):
        c = Client()
        c.login(username="rep", password="pass12345")
        r1 = c.post(f"/report/track/{self.track.id}/", {"reason": "spam"})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["ok"])

        r2 = c.post(f"/report/track/{self.track.id}/", {"reason": "spam"})
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(r2.json()["error"], "already_reported_today")

        self.assertEqual(Report.objects.count(), 1)


class ReportProfileViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.reporter = make_user("reporter_p")
        self.target = make_user("target_p")

    def tearDown(self):
        cache.clear()

    def test_requires_login(self):
        c = Client()
        resp = c.post(f"/report/profile/@{self.target.username}/")
        self.assertEqual(resp.status_code, 302)

    def test_cannot_report_self(self):
        c = Client()
        c.login(username="reporter_p", password="pass12345")
        resp = c.post(f"/report/profile/@{self.reporter.username}/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "cannot_report_self")

    def test_unknown_username_404s(self):
        c = Client()
        c.login(username="reporter_p", password="pass12345")
        resp = c.post("/report/profile/@doesnotexist/")
        self.assertEqual(resp.status_code, 404)

    def test_valid_report_creates_record(self):
        c = Client()
        c.login(username="reporter_p", password="pass12345")
        resp = c.post(
            f"/report/profile/@{self.target.username}/",
            {"reason": "impersonation", "details": "fake account"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        report = Report.objects.get(target_user=self.target)
        self.assertEqual(report.reporter, self.reporter)
        self.assertEqual(report.reason, "impersonation")

    def test_once_per_day_per_target(self):
        c = Client()
        c.login(username="reporter_p", password="pass12345")
        r1 = c.post(f"/report/profile/@{self.target.username}/", {"reason": "spam"})
        self.assertEqual(r1.status_code, 200)
        r2 = c.post(f"/report/profile/@{self.target.username}/", {"reason": "spam"})
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(Report.objects.filter(target_user=self.target).count(), 1)


class TrackQueueViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_q")
        self.regular = make_user("regular_q")
        self.creator = make_user("creator_q")

    def test_anonymous_gets_404(self):
        resp = self.client.get(reverse("moderation_track_queue"))
        self.assertEqual(resp.status_code, 404)

    def test_non_staff_gets_404(self):
        self.client.login(username="regular_q", password="pass12345")
        resp = self.client.get(reverse("moderation_track_queue"))
        self.assertEqual(resp.status_code, 404)

    def test_staff_sees_only_submitted_and_pending_tracks(self):
        submitted = Track.objects.create(
            creator=self.creator, title="Submitted", content_type=Track.ContentType.MUSIC,
            status=Track.Status.SUBMITTED,
        )
        Track.objects.create(
            creator=self.creator, title="Draft", content_type=Track.ContentType.MUSIC,
            status=Track.Status.DRAFT,
        )
        Track.objects.create(
            creator=self.creator, title="Approved", content_type=Track.ContentType.MUSIC,
            status=Track.Status.APPROVED,
        )
        self.client.login(username="staff_q", password="pass12345")
        resp = self.client.get(reverse("moderation_track_queue"))
        self.assertEqual(resp.status_code, 200)
        titles = {t.title for t in resp.context["tracks"]}
        self.assertEqual(titles, {"Submitted"})
        self.assertEqual(submitted.status, Track.Status.SUBMITTED)


class ApproveTrackViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_a")
        self.regular = make_user("regular_a")
        self.creator = make_user("creator_a")
        self.track = Track.objects.create(
            creator=self.creator, title="Pending track", content_type=Track.ContentType.MUSIC,
            status=Track.Status.SUBMITTED, visibility=Track.Visibility.PRIVATE,
        )

    def test_anonymous_gets_404(self):
        resp = self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 404)

    def test_non_staff_gets_404(self):
        self.client.login(username="regular_a", password="pass12345")
        resp = self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 404)

    def test_get_not_allowed(self):
        self.client.login(username="staff_a", password="pass12345")
        resp = self.client.get(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 405)

    def test_approve_sets_status_visibility_and_published_at(self):
        self.client.login(username="staff_a", password="pass12345")
        resp = self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 302)
        self.track.refresh_from_db()
        self.assertEqual(self.track.status, Track.Status.APPROVED)
        self.assertEqual(self.track.visibility, Track.Visibility.PUBLIC)
        self.assertIsNotNone(self.track.published_at)

    def test_approve_writes_audit_log(self):
        self.client.login(username="staff_a", password="pass12345")
        self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        log = AuditLog.objects.get(track=self.track)
        self.assertEqual(log.action, "approve_track")
        self.assertEqual(log.actor, self.staff)

    def test_approve_notifies_creator(self):
        self.client.login(username="staff_a", password="pass12345")
        self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertTrue(
            Notification.objects.filter(recipient=self.creator, verb="track_approved", track=self.track).exists()
        )

    def test_reapproving_is_idempotent_no_duplicate_notification_or_audit_log(self):
        """Regression: re-clicking approve used to resend the notification,
        rewrite AuditLog, and bump published_at every single time."""
        self.client.login(username="staff_a", password="pass12345")
        self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.track.refresh_from_db()
        first_published_at = self.track.published_at

        resp = self.client.post(reverse("moderation_approve_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 302)

        self.track.refresh_from_db()
        self.assertEqual(self.track.published_at, first_published_at)
        self.assertEqual(
            Notification.objects.filter(recipient=self.creator, verb="track_approved", track=self.track).count(),
            1,
        )
        self.assertEqual(AuditLog.objects.filter(track=self.track, action="approve_track").count(), 1)


class RejectTrackViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_r")
        self.regular = make_user("regular_r")
        self.creator = make_user("creator_r")
        self.track = Track.objects.create(
            creator=self.creator, title="Pending track", content_type=Track.ContentType.MUSIC,
            status=Track.Status.SUBMITTED,
        )

    def test_non_staff_gets_404(self):
        self.client.login(username="regular_r", password="pass12345")
        resp = self.client.post(reverse("moderation_reject_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 404)

    def test_reject_with_reason_sets_status_and_reason(self):
        self.client.login(username="staff_r", password="pass12345")
        resp = self.client.post(
            reverse("moderation_reject_track", args=[self.track.id]), {"reason": "کیفیت پایین"}
        )
        self.assertEqual(resp.status_code, 302)
        self.track.refresh_from_db()
        self.assertEqual(self.track.status, Track.Status.REJECTED)
        self.assertEqual(self.track.reject_reason, "کیفیت پایین")

    def test_reject_without_reason_uses_default(self):
        self.client.login(username="staff_r", password="pass12345")
        self.client.post(reverse("moderation_reject_track", args=[self.track.id]))
        self.track.refresh_from_db()
        self.assertEqual(self.track.reject_reason, "رد شد")

    def test_reject_writes_audit_log_with_reason_metadata(self):
        self.client.login(username="staff_r", password="pass12345")
        self.client.post(
            reverse("moderation_reject_track", args=[self.track.id]), {"reason": "spam"}
        )
        log = AuditLog.objects.get(track=self.track, action="reject_track")
        self.assertEqual(log.metadata["reason"], "spam")

    def test_reject_notifies_creator(self):
        self.client.login(username="staff_r", password="pass12345")
        self.client.post(reverse("moderation_reject_track", args=[self.track.id]))
        self.assertTrue(
            Notification.objects.filter(recipient=self.creator, verb="track_rejected", track=self.track).exists()
        )

    def test_rerejecting_is_idempotent_no_duplicate_notification(self):
        self.client.login(username="staff_r", password="pass12345")
        self.client.post(reverse("moderation_reject_track", args=[self.track.id]))
        resp = self.client.post(reverse("moderation_reject_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            Notification.objects.filter(recipient=self.creator, verb="track_rejected", track=self.track).count(),
            1,
        )


class ReportQueueViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("staff_rq")
        self.regular = make_user("regular_rq")
        self.reporter = make_user("reporter_rq")
        self.creator = make_user("creator_rq")
        self.track = Track.objects.create(
            creator=self.creator, title="Reported", content_type=Track.ContentType.MUSIC,
        )
        Report.objects.create(
            reporter=self.reporter, target_type=Report.TargetType.TRACK,
            track=self.track, reason=Report.Reason.SPAM,
        )

    def test_non_staff_gets_404(self):
        self.client.login(username="regular_rq", password="pass12345")
        resp = self.client.get(reverse("moderation_report_queue"))
        self.assertEqual(resp.status_code, 404)

    def test_staff_sees_reports(self):
        self.client.login(username="staff_rq", password="pass12345")
        resp = self.client.get(reverse("moderation_report_queue"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["reports"]), 1)
