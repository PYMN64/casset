from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from core.test_utils import make_superuser, make_user
from interactions.models import Comment
from notifications.models import Notification
from tracks.models import Track

from .models import AuditLog, Report
from .services import (
    AUTO_HIDE_REPORT_THRESHOLD,
    approve_track,
    check_and_auto_hide_comment,
    reject_track,
    restore_comment,
    set_verified,
    suspend_user,
    update_report_status,
)


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


class ReportCommentViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.creator = make_user("cc_creator")
        self.author = make_user("cc_author")
        self.track = Track.objects.create(
            creator=self.creator, title="T", slug="cc-t", status=Track.Status.APPROVED
        )
        self.comment = Comment.objects.create(
            track=self.track, author=self.author, body="hello"
        )

    def tearDown(self):
        cache.clear()

    def test_requires_login(self):
        resp = self.client.post(reverse("report_comment", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)

    def test_valid_report_creates_record(self):
        reporter = make_user("cc_reporter")
        self.client.login(username="cc_reporter", password="pass12345")
        resp = self.client.post(
            reverse("report_comment", args=[self.comment.id]),
            {"reason": "spam"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        report = Report.objects.get(comment=self.comment)
        self.assertEqual(report.reporter, reporter)
        self.assertEqual(report.target_type, Report.TargetType.COMMENT)

    def test_once_per_day_per_comment(self):
        make_user("cc_reporter2")
        self.client.login(username="cc_reporter2", password="pass12345")
        r1 = self.client.post(reverse("report_comment", args=[self.comment.id]))
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post(reverse("report_comment", args=[self.comment.id]))
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(Report.objects.filter(comment=self.comment).count(), 1)

    def test_auto_hides_after_threshold_reports(self):
        for i in range(AUTO_HIDE_REPORT_THRESHOLD):
            make_user(f"cc_bulk_{i}")
            self.client.login(username=f"cc_bulk_{i}", password="pass12345")
            resp = self.client.post(reverse("report_comment", args=[self.comment.id]))
            self.assertEqual(resp.status_code, 200)
            self.client.logout()

        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_public)
        self.assertTrue(
            AuditLog.objects.filter(
                target_type=AuditLog.TargetType.COMMENT, action="auto_hide_comment"
            ).exists()
        )
        self.assertTrue(resp.json()["auto_hidden"])


class AutoHideCommentServiceTests(TestCase):
    def setUp(self):
        self.creator = make_user("ah_creator")
        self.author = make_user("ah_author")
        self.track = Track.objects.create(
            creator=self.creator, title="T", slug="ah-t", status=Track.Status.APPROVED
        )
        self.comment = Comment.objects.create(
            track=self.track, author=self.author, body="hi"
        )

    def test_no_op_below_threshold(self):
        Report.objects.create(
            reporter=self.creator, target_type=Report.TargetType.COMMENT,
            comment=self.comment, reason=Report.Reason.SPAM,
        )
        hidden = check_and_auto_hide_comment(comment=self.comment)
        self.assertFalse(hidden)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_public)

    def test_already_hidden_comment_is_noop(self):
        self.comment.is_public = False
        self.comment.save(update_fields=["is_public"])
        hidden = check_and_auto_hide_comment(comment=self.comment)
        self.assertFalse(hidden)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_rejected_reports_dont_count_toward_threshold(self):
        for i in range(AUTO_HIDE_REPORT_THRESHOLD):
            Report.objects.create(
                reporter=make_user(f"ah_r_{i}"), target_type=Report.TargetType.COMMENT,
                comment=self.comment, reason=Report.Reason.SPAM,
                status=Report.Status.REJECTED,
            )
        hidden = check_and_auto_hide_comment(comment=self.comment)
        self.assertFalse(hidden)


class ApproveRejectTrackServiceTests(TestCase):
    """Phase 3: approve_track/reject_track moved from views.py into
    services.py so the staff queue and the auto-approve-on-submit path
    (uploads/views.py) share one implementation."""

    def setUp(self):
        self.staff = make_superuser("svc_staff")
        self.creator = make_user("svc_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="T", status=Track.Status.SUBMITTED,
            visibility=Track.Visibility.PRIVATE,
        )

    def test_approve_sets_status_visibility_published_at(self):
        ok = approve_track(track=self.track, actor=self.staff)
        self.assertTrue(ok)
        self.track.refresh_from_db()
        self.assertEqual(self.track.status, Track.Status.APPROVED)
        self.assertEqual(self.track.visibility, Track.Visibility.PUBLIC)
        self.assertIsNotNone(self.track.published_at)

    def test_approve_is_idempotent(self):
        approve_track(track=self.track, actor=self.staff)
        second = approve_track(track=self.track, actor=self.staff)
        self.assertFalse(second)
        self.assertEqual(AuditLog.objects.filter(track=self.track, action="approve_track").count(), 1)

    def test_approve_actor_none_means_system_audit_log(self):
        approve_track(track=self.track, actor=None)
        log = AuditLog.objects.get(track=self.track, action="approve_track")
        self.assertIsNone(log.actor)
        self.assertTrue(log.metadata["auto"])

    def test_approve_actor_present_means_manual_audit_log(self):
        approve_track(track=self.track, actor=self.staff)
        log = AuditLog.objects.get(track=self.track, action="approve_track")
        self.assertEqual(log.actor, self.staff)
        self.assertFalse(log.metadata["auto"])

    def test_reject_sets_status_and_reason(self):
        ok = reject_track(track=self.track, actor=self.staff, reason="کیفیت پایین")
        self.assertTrue(ok)
        self.track.refresh_from_db()
        self.assertEqual(self.track.status, Track.Status.REJECTED)
        self.assertEqual(self.track.reject_reason, "کیفیت پایین")

    def test_reject_is_idempotent(self):
        reject_track(track=self.track, actor=self.staff)
        second = reject_track(track=self.track, actor=self.staff)
        self.assertFalse(second)


class UpdateReportStatusViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("ur_staff")
        self.regular = make_user("ur_regular")
        self.reporter = make_user("ur_reporter")
        self.track = Track.objects.create(creator=make_user("ur_creator"), title="T")
        self.report = Report.objects.create(
            reporter=self.reporter, target_type=Report.TargetType.TRACK,
            track=self.track, reason=Report.Reason.SPAM,
        )

    def test_non_staff_gets_404(self):
        self.client.login(username="ur_regular", password="pass12345")
        resp = self.client.post(
            reverse("moderation_update_report", args=[self.report.id]), {"status": "actioned"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_valid_status_update(self):
        self.client.login(username="ur_staff", password="pass12345")
        resp = self.client.post(
            reverse("moderation_update_report", args=[self.report.id]),
            {"status": "reviewed", "note": "بررسی شد"},
        )
        self.assertEqual(resp.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.REVIEWED)
        self.assertEqual(self.report.admin_note, "بررسی شد")
        self.assertEqual(self.report.reviewed_by, self.staff)
        self.assertIsNotNone(self.report.reviewed_at)

    def test_invalid_status_rejected(self):
        self.client.login(username="ur_staff", password="pass12345")
        resp = self.client.post(
            reverse("moderation_update_report", args=[self.report.id]),
            {"status": "not_a_real_status"},
        )
        self.assertEqual(resp.status_code, 400)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.PENDING)

    def test_update_writes_audit_log(self):
        update_report_status(report=self.report, actor=self.staff, status=Report.Status.ACTIONED)
        self.assertTrue(
            AuditLog.objects.filter(report=self.report, action="report_actioned").exists()
        )


class RestoreCommentViewTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("rc_staff")
        self.regular = make_user("rc_regular")
        self.track = Track.objects.create(creator=make_user("rc_creator"), title="T")
        self.comment = Comment.objects.create(
            track=self.track, author=make_user("rc_author"), body="x", is_public=False
        )

    def test_non_staff_gets_404(self):
        self.client.login(username="rc_regular", password="pass12345")
        resp = self.client.post(reverse("moderation_restore_comment", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 404)

    def test_staff_restores_comment(self):
        self.client.login(username="rc_staff", password="pass12345")
        resp = self.client.post(reverse("moderation_restore_comment", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_public)

    def test_restore_service_is_idempotent(self):
        restore_comment(comment=self.comment, actor=self.staff)
        second = restore_comment(comment=self.comment, actor=self.staff)
        self.assertFalse(second)
        self.assertEqual(
            AuditLog.objects.filter(action="restore_comment", metadata__comment_id=self.comment.id).count(), 1
        )


class SuspendUnsuspendProfileTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("sp_staff")
        self.regular = make_user("sp_regular")
        self.target = make_user("sp_target")
        self.other_staff = make_superuser("sp_staff2")

    def test_non_staff_gets_404(self):
        self.client.login(username="sp_regular", password="pass12345")
        resp = self.client.post(reverse("moderation_suspend_profile", args=[self.target.username]))
        self.assertEqual(resp.status_code, 404)

    def test_staff_suspends_account(self):
        self.client.login(username="sp_staff", password="pass12345")
        resp = self.client.post(
            reverse("moderation_suspend_profile", args=[self.target.username]),
            {"reason": "هرزنامه مکرر"},
        )
        self.assertEqual(resp.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(self.target.profile.suspended_reason, "هرزنامه مکرر")
        self.assertIsNotNone(self.target.profile.suspended_at)
        self.assertTrue(
            AuditLog.objects.filter(target_user=self.target, action="suspend_user").exists()
        )

    def test_cannot_suspend_staff(self):
        ok = suspend_user(user=self.other_staff, actor=self.staff)
        self.assertFalse(ok)
        self.other_staff.refresh_from_db()
        self.assertTrue(self.other_staff.is_active)

    def test_unsuspend_restores_login(self):
        suspend_user(user=self.target, actor=self.staff)
        self.client.login(username="sp_staff", password="pass12345")
        resp = self.client.post(reverse("moderation_unsuspend_profile", args=[self.target.username]))
        self.assertEqual(resp.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertIsNone(self.target.profile.suspended_at)

    def test_suspend_is_idempotent(self):
        suspend_user(user=self.target, actor=self.staff)
        second = suspend_user(user=self.target, actor=self.staff)
        self.assertFalse(second)


class SetVerifiedTests(TestCase):
    def setUp(self):
        self.staff = make_superuser("vf_staff")
        self.regular = make_user("vf_regular")
        self.creator = make_user("vf_creator")

    def test_grants_badge(self):
        ok = set_verified(user=self.creator, actor=self.staff, verified=True)
        self.assertTrue(ok)
        self.creator.profile.refresh_from_db()
        self.assertTrue(self.creator.profile.is_verified)
        self.assertTrue(
            AuditLog.objects.filter(target_user=self.creator, action="set_verified").exists()
        )

    def test_revokes_badge(self):
        set_verified(user=self.creator, actor=self.staff, verified=True)
        ok = set_verified(user=self.creator, actor=self.staff, verified=False)
        self.assertTrue(ok)
        self.creator.profile.refresh_from_db()
        self.assertFalse(self.creator.profile.is_verified)

    def test_setting_same_value_is_noop(self):
        second = set_verified(user=self.creator, actor=self.staff, verified=False)
        self.assertFalse(second)

    def test_toggle_view_requires_staff(self):
        self.client.login(username="vf_regular", password="pass12345")
        resp = self.client.post(reverse("staff:toggle_verified", args=[self.creator.id]))
        self.assertNotEqual(resp.status_code, 200)
        self.creator.profile.refresh_from_db()
        self.assertFalse(self.creator.profile.is_verified)

    def test_toggle_view_flips_state(self):
        self.client.login(username="vf_staff", password="pass12345")
        resp = self.client.post(reverse("staff:toggle_verified", args=[self.creator.id]))
        self.assertEqual(resp.status_code, 302)
        self.creator.profile.refresh_from_db()
        self.assertTrue(self.creator.profile.is_verified)

        self.client.post(reverse("staff:toggle_verified", args=[self.creator.id]))
        self.creator.profile.refresh_from_db()
        self.assertFalse(self.creator.profile.is_verified)
