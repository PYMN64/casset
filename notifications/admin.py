"""notifications/admin.py — Staff dashboard for notification monitoring."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "verb",
        "actor",
        "track_link",
        "actor_count",
        "is_read",
        "created_at",
    )
    list_filter = ("verb", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username", "track__title")
    readonly_fields = (
        "recipient", "verb", "actor", "track", "comment",
        "group_key", "actor_count", "is_read", "read_at",
        "extra", "created_at", "updated_at",
    )
    ordering = ("-created_at",)

    def track_link(self, obj):
        if obj.track:
            return format_html(
                '<a href="/admin/tracks/track/{}/change/">{}</a>',
                obj.track.pk,
                obj.track.title[:40],
            )
        return "-"
    track_link.short_description = "Track"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Notifications are append-only — only superuser can delete for cleanup.
        return request.user.is_superuser
