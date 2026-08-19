"""moderation/services.py — Comment moderation-lite.

Auto-hide is intentionally simple for MVP: once a comment collects
AUTO_HIDE_REPORT_THRESHOLD distinct pending/reviewed reports, it's flipped
to is_public=False and an AuditLog row records the automated action. A human
can still review it later via the report queue and restore/reject as usual —
this only removes the comment from public view fast, it doesn't delete data.
"""

import logging

from .models import AuditLog, Report

logger = logging.getLogger("casset.moderation")

AUTO_HIDE_REPORT_THRESHOLD = 3


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
