from django.conf import settings
from django.db import models


class Report(models.Model):
    class TargetType(models.TextChoices):
        TRACK = 'track', 'Track'
        PROFILE = 'profile', 'Profile'
        COMMENT = 'comment', 'Comment'

    class Reason(models.TextChoices):
        IMPERSONATION = 'impersonation', 'Impersonation / Username claim'
        COPYRIGHT = 'copyright', 'Copyright'
        SPAM = 'spam', 'Spam / Fake activity'
        ABUSE = 'abuse', 'Abuse / Harassment'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        ACTIONED = 'actioned', 'Actioned'
        REJECTED = 'rejected', 'Rejected'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_made')
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    # Track, profile, or comment target
    track = models.ForeignKey('tracks.Track', on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='reports_received')
    comment = models.ForeignKey('interactions.Comment', on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reported_username = models.CharField(max_length=150, blank=True)

    reason = models.CharField(max_length=32, choices=Reason.choices)
    details = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_reviewed')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['target_type','status','created_at'])]

    def __str__(self):
        return f"Report#{self.pk} {self.target_type} {self.reason}"


class AuditLogImmutableError(Exception):
    """Raised on any attempt to update or delete an existing AuditLog row —
    the audit trail is the record of who did what to whom; letting it be
    edited or removed after the fact would defeat its only purpose."""


class AuditLogQuerySet(models.QuerySet):
    """Blocks the bulk paths (`.filter(...).update()/.delete()`) that bypass
    a model instance's save()/delete() overrides below. Scoped to ORM usage
    (raw SQL is out of reach for a Python-level guard) — matches how the
    rest of the project enforces immutability elsewhere (e.g. PointLedger's
    admin has no delete action; see plays/admin.py)."""

    def update(self, **kwargs):
        raise AuditLogImmutableError("AuditLog rows are immutable — bulk update is not allowed.")

    def bulk_update(self, objs, fields, **kwargs):
        raise AuditLogImmutableError("AuditLog rows are immutable — bulk update is not allowed.")

    def delete(self):
        raise AuditLogImmutableError("AuditLog rows are immutable — bulk delete is not allowed.")


class AuditLog(models.Model):
    """Immutable audit log for moderation and sensitive actions.

    Enforced at the ORM level (S11): once a row has a pk, save() refuses to
    write it again, and delete() always refuses — on both the instance and
    the queryset (AuditLogQuerySet above), so `.filter(...).update()`/
    `.delete()` are blocked the same as `instance.save()`/`instance.delete()`.
    Only `objects.create(...)` (a fresh insert) is allowed.
    """

    class TargetType(models.TextChoices):
        TRACK = "track", "Track"
        REPORT = "report", "Report"
        PROFILE = "profile", "Profile"
        COMMENT = "comment", "Comment"
        PAYOUT = "payout", "Payout"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_actions")
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    track = models.ForeignKey('tracks.Track', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    report = models.ForeignKey('moderation.Report', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_targets')
    payout = models.ForeignKey('billing.PayoutRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')

    action = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['target_type','action','created_at'])]

    def __str__(self):
        return f"Audit#{self.pk} {self.target_type}:{self.action}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AuditLogImmutableError(
                "AuditLog rows are immutable — cannot update an existing record."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditLogImmutableError("AuditLog rows are immutable — cannot delete a record.")
