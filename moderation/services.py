"""moderation/services.py — Moderation decisions and enforcement.

All state-changing moderation actions (approve/reject a track, act on a
report, suspend an account, restore a hidden comment) live here so staff
views and automated paths (e.g. the platform's auto-approve setting) share
one implementation and one audit trail. Views only handle HTTP concerns.

`actor=None` means the action was taken by the system, not a human staff
member (e.g. auto-approve on submit, or the auto-hide-after-N-reports path).
"""

import logging

from django.utils import timezone

from .models import AuditLog, Report

logger = logging.getLogger("casset.moderation")

AUTO_HIDE_REPORT_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Comments — auto-hide / restore
# ---------------------------------------------------------------------------

def check_and_auto_hide_comment(*, comment) -> bool:
    """Hide a comment once it has enough open reports. Returns True if hidden
    by this call. Idempotent — a comment already hidden is a no-op."""
    if not comment.is_public:
        return False

    open_reports = Report.objects.filter(
        target_type=Report.TargetType.COMMENT,
        comment=comment,
        status__in=[Report.Status.PENDING, Report.Status.REVIEWED],
    ).count()

    if open_reports < AUTO_HIDE_REPORT_THRESHOLD:
        return False

    comment.is_public = False
    comment.save(update_fields=["is_public"])
    AuditLog.objects.create(
        actor=None,
        target_type=AuditLog.TargetType.COMMENT,
        action="auto_hide_comment",
        metadata={"comment_id": comment.id, "report_count": open_reports},
    )
    logger.info("auto_hide_comment: comment=%s reports=%d", comment.id, open_reports)
    return True


def restore_comment(*, comment, actor) -> bool:
    """Un-hide a comment (staff override of auto-hide or a manual takedown).
    Idempotent — an already-visible comment is a no-op."""
    if comment.is_public:
        return False
    comment.is_public = True
    comment.save(update_fields=["is_public"])
    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.COMMENT,
        action="restore_comment",
        metadata={"comment_id": comment.id},
    )
    logger.info("restore_comment: comment=%s actor=%s", comment.id, getattr(actor, "pk", None))
    return True


# ---------------------------------------------------------------------------
# Tracks — approve / reject
#
# Shared by the staff review queue AND the auto-approve path (uploads/views.py
# submit_track, gated by PlatformSetting.auto_approve_tracks). Saving with
# status=APPROVED/REJECTED triggers notifications/signals.py the same way
# regardless of who called save() — human or automated — so notification
# behavior is identical either way.
# ---------------------------------------------------------------------------

def approve_track(*, track, actor) -> bool:
    """Approve a track. Idempotent — re-approving is a no-op returning False."""
    from tracks.models import Track

    if track.status == Track.Status.APPROVED:
        return False
    track.status = Track.Status.APPROVED
    track.reject_reason = ""
    track.published_at = timezone.now()
    if track.visibility == Track.Visibility.PRIVATE:
        track.visibility = Track.Visibility.PUBLIC
    track.save(update_fields=["status", "reject_reason", "published_at", "visibility"])
    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.TRACK,
        track=track,
        action="approve_track",
        metadata={"auto": actor is None},
    )
    return True


def reject_track(*, track, actor, reason: str = "") -> bool:
    """Reject a track. Idempotent — re-rejecting is a no-op returning False."""
    from tracks.models import Track

    if track.status == Track.Status.REJECTED:
        return False
    track.status = Track.Status.REJECTED
    track.reject_reason = (reason or "").strip()[:240] or "رد شد"
    track.save(update_fields=["status", "reject_reason"])
    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.TRACK,
        track=track,
        action="reject_track",
        metadata={"reason": track.reject_reason},
    )
    return True


# ---------------------------------------------------------------------------
# Reports — staff review actions
# ---------------------------------------------------------------------------

def update_report_status(*, report, actor, status: str, note: str = "") -> bool:
    """Move a report to reviewed/actioned/rejected. Returns False for an
    unknown status (caller's job to validate against Report.Status choices
    before calling, this is the last-line guard)."""
    valid = {c for c, _ in Report.Status.choices}
    if status not in valid:
        return False

    report.status = status
    if note:
        report.admin_note = note[:1000]
    report.reviewed_by = actor
    report.reviewed_at = timezone.now()
    report.save(update_fields=["status", "admin_note", "reviewed_by", "reviewed_at"])
    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.REPORT,
        report=report,
        action=f"report_{status}",
    )
    return True


# ---------------------------------------------------------------------------
# Accounts — suspend / unsuspend
#
# Suspension is enforced via Django's built-in User.is_active — password
# login already refuses inactive users (AuthenticationForm.confirm_login_
# allowed). Phone-OTP login does NOT go through that form, so
# accounts/views.py::phone_verify_view checks is_active explicitly too.
# ---------------------------------------------------------------------------

def suspend_user(*, user, actor, reason: str = "") -> bool:
    """Suspend an account (blocks future login). Never suspends staff —
    a report queue misclick shouldn't be able to lock out an admin."""
    if not user.is_active or user.is_staff:
        return False

    user.is_active = False
    user.save(update_fields=["is_active"])

    profile = user.profile
    profile.suspended_at = timezone.now()
    profile.suspended_reason = (reason or "").strip()[:240]
    profile.save(update_fields=["suspended_at", "suspended_reason"])

    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.PROFILE,
        target_user=user,
        action="suspend_user",
        metadata={"reason": profile.suspended_reason},
    )
    logger.info("suspend_user: user=%s actor=%s", user.pk, getattr(actor, "pk", None))
    return True


def set_verified(*, user, actor, verified: bool) -> bool:
    """Grant/revoke the verified badge. Idempotent — setting the same value
    twice is a no-op returning False, same convention as the rest of this
    module (approve_track, suspend_user, ...)."""
    profile = user.profile
    if profile.is_verified == verified:
        return False

    profile.is_verified = verified
    profile.save(update_fields=["is_verified"])

    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.PROFILE,
        target_user=user,
        action="set_verified" if verified else "unset_verified",
    )
    logger.info("set_verified: user=%s verified=%s actor=%s", user.pk, verified, getattr(actor, "pk", None))
    return True


def unsuspend_user(*, user, actor) -> bool:
    if user.is_active:
        return False

    user.is_active = True
    user.save(update_fields=["is_active"])

    profile = user.profile
    profile.suspended_at = None
    profile.suspended_reason = ""
    profile.save(update_fields=["suspended_at", "suspended_reason"])

    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.PROFILE,
        target_user=user,
        action="unsuspend_user",
    )
    logger.info("unsuspend_user: user=%s actor=%s", user.pk, getattr(actor, "pk", None))
    return True
