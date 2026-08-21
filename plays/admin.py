"""plays/admin.py — Staff-facing views for plays, points, and fraud signals."""

from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import DailyTrackStat, FraudFlag, PlaybackSession, PlayEvent, PointLedger

# ---------------------------------------------------------------------------
# PlayEvent
# ---------------------------------------------------------------------------

@admin.register(PlayEvent)
class PlayEventAdmin(admin.ModelAdmin):
    list_display = (
        "id", "track", "user", "ip_hash_short",
        "day_key", "point_awarded", "created_at",
    )
    list_filter = ("point_awarded", "day_key")
    search_fields = ("track__title", "user__username", "ip_hash")
    readonly_fields = ("track", "user", "ip_hash", "ua_hash", "day_key", "created_at")
    ordering = ("-created_at",)

    def ip_hash_short(self, obj):
        return obj.ip_hash[:12] + "..."
    ip_hash_short.short_description = "IP hash"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# PointLedger
# ---------------------------------------------------------------------------

@admin.register(PointLedger)
class PointLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "delta_display", "reason",
        "track_id_snapshot", "ip_hash_short", "note_short", "created_at",
    )
    list_filter = ("reason", "created_at")
    search_fields = ("user__username", "ip_hash_snapshot", "note")
    readonly_fields = (
        "user", "delta", "reason", "play_event",
        "track_id_snapshot", "ip_hash_snapshot", "note", "created_at",
    )
    ordering = ("-created_at",)

    # Summary at the top of changelist
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        totals = qs.aggregate(
            total_awarded=Sum("delta"),
        )
        extra_context["ledger_summary"] = (
            f"Total points awarded (filtered): "
            f"{totals['total_awarded'] or 0}"
        )
        return super().changelist_view(request, extra_context=extra_context)

    def delta_display(self, obj):
        colour = "green" if obj.delta > 0 else ("grey" if obj.delta == 0 else "red")
        sign = "+" if obj.delta > 0 else ""
        return format_html(
            '<b style="color:{}">{}{}</b>', colour, sign, obj.delta
        )
    delta_display.short_description = "Delta"

    def ip_hash_short(self, obj):
        return obj.ip_hash_snapshot[:12] + "..." if obj.ip_hash_snapshot else "-"
    ip_hash_short.short_description = "IP hash"

    def note_short(self, obj):
        return obj.note[:60] + "..." if len(obj.note) > 60 else obj.note
    note_short.short_description = "Note"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Ledger rows are immutable — never delete.
        return False


# ---------------------------------------------------------------------------
# FraudFlag
# ---------------------------------------------------------------------------

@admin.register(FraudFlag)
class FraudFlagAdmin(admin.ModelAdmin):
    list_display = (
        "id", "flag_type", "score_display", "user",
        "track", "ip_hash_short", "note_short", "created_at",
    )
    list_filter = ("flag_type", "created_at")
    search_fields = ("user__username", "ip_hash", "note", "track__title")
    readonly_fields = (
        "user", "track", "ip_hash", "flag_type", "score", "note", "created_at",
    )
    ordering = ("-created_at",)

    def score_display(self, obj):
        colour = "red" if obj.score >= 5 else ("orange" if obj.score >= 3 else "grey")
        return format_html('<b style="color:{}">{}</b>', colour, obj.score)
    score_display.short_description = "Score"

    def ip_hash_short(self, obj):
        return obj.ip_hash[:12] + "..." if obj.ip_hash else "-"
    ip_hash_short.short_description = "IP hash"

    def note_short(self, obj):
        return obj.note[:60] + "..." if len(obj.note) > 60 else obj.note
    note_short.short_description = "Note"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# PlaybackSession
# ---------------------------------------------------------------------------

@admin.register(PlaybackSession)
class PlaybackSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "track", "user", "status", "source",
        "max_progress_ratio", "started_at", "ended_at", "disqualify_reason",
    )
    list_filter = ("status", "source", "started_at")
    search_fields = ("track__title", "user__username", "ip_hash")
    readonly_fields = (
        "track", "user", "play_event", "ip_hash", "ua_hash", "source",
        "status", "disqualify_reason", "max_progress_ratio",
        "started_at", "last_seen_at", "ended_at",
    )
    ordering = ("-started_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# DailyTrackStat
# ---------------------------------------------------------------------------

@admin.register(DailyTrackStat)
class DailyTrackStatAdmin(admin.ModelAdmin):
    list_display = ("id", "track", "day", "plays", "unique_plays", "points_awarded")
    list_filter = ("day",)
    search_fields = ("track__title",)
    ordering = ("-day",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
