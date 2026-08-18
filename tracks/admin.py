from django.contrib import admin
from .models import Track, Genre, Album, Tag


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ("name", "slug")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name", "slug")


class TrackInline(admin.TabularInline):
    """Show tracks belonging to an album directly inside AlbumAdmin."""
    model = Track
    fields = ("title", "content_type", "status", "visibility", "created_at")
    readonly_fields = ("title", "content_type", "status", "visibility", "created_at")
    extra = 0
    show_change_link = True
    can_delete = False


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "creator", "content_type", "is_public", "track_count", "created_at")
    list_filter = ("content_type", "is_public", "created_at")
    search_fields = ("title", "creator__username")
    autocomplete_fields = ("creator",)
    readonly_fields = ("created_at",)
    inlines = [TrackInline]

    def track_count(self, obj):
        return obj.tracks.count()
    track_count.short_description = "Tracks"


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "creator", "content_type", "status", "visibility", "play_count", "like_count", "created_at")
    list_filter = ("status", "content_type", "visibility", "created_at")
    search_fields = ("title", "creator__username", "slug")
    autocomplete_fields = ("creator", "album")
    readonly_fields = ("slug", "created_at", "updated_at", "submitted_at", "published_at")
    fieldsets = (
        (None, {
            "fields": ("creator", "title", "slug", "content_type", "album")
        }),
        ("محتوا", {
            "fields": ("description", "language", "explicit", "allow_comments")
        }),
        ("فایل‌ها", {
            "fields": ("cover", "audio", "video", "duration_seconds")
        }),
        ("وضعیت انتشار", {
            "fields": ("status", "visibility", "reject_reason",
                        "submitted_at", "published_at")
        }),
        ("آمار", {
            "fields": ("play_count", "like_count")
        }),
        ("تگ و ژانر", {
            "fields": ("genres", "tags")
        }),
        ("تاریخ‌ها", {
            "fields": ("created_at", "updated_at")
        }),
    )
