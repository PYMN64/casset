from django.contrib import admin

from .models import AuditLog, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id','target_type','reason','status','created_at','reporter','target_user','track','comment')
    list_filter = ('target_type','reason','status','created_at')
    search_fields = ('reported_username','details','admin_note','target_user__username','reporter__username','track__title')
    autocomplete_fields = ('reporter','target_user','track','comment','reviewed_by')
    readonly_fields = ('created_at','reviewed_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only by design: the audit trail is the record of who did what to
    whom. Letting staff edit or delete entries from the admin would defeat
    its only purpose, so every field is read-only and add/change/delete are
    all refused — entries are written exclusively by the service layer
    (moderation/services.py, billing/services.py)."""

    list_display = ('id','created_at','actor','target_type','action','target_user','track','report','payout')
    list_filter = ('target_type','action','created_at')
    search_fields = ('action','actor__username','target_user__username','track__title')
    readonly_fields = ('actor','target_type','track','report','target_user','payout','action','metadata','created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
