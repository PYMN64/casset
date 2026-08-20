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


class AuditLog(models.Model):
    """Immutable audit log for moderation and sensitive actions."""

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

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['target_type','action','created_at'])]

    def __str__(self):
        return f"Audit#{self.pk} {self.target_type}:{self.action}"
