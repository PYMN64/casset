"""interactions/admin.py — Staff views for social interactions."""

from django.contrib import admin

from .models import Comment, CommentLike, CreatorBlock, CreatorFollow, TrackFavorite, TrackLike


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "track", "author", "short_body", "is_public", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("body", "author__username", "track__title")
    autocomplete_fields = ("track", "author")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def short_body(self, obj):
        text = obj.body or ""
        return text[:60] + ("…" if len(text) > 60 else "")
    short_body.short_description = "متن"


@admin.register(TrackLike)
class TrackLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "track__title")
    autocomplete_fields = ("user", "track")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "comment", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user", "comment")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(CreatorFollow)
class CreatorFollowAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "creator", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "creator__username")
    autocomplete_fields = ("user", "creator")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(TrackFavorite)
class TrackFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "track__title")
    autocomplete_fields = ("user", "track")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(CreatorBlock)
class CreatorBlockAdmin(admin.ModelAdmin):
    list_display = ("id", "creator", "blocked_user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("creator__username", "blocked_user__username")
    autocomplete_fields = ("creator", "blocked_user")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
