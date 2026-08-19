from django.contrib import admin

from .models import PlatformSetting


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    """Single place for platform-wide controls.

    Keep a single row; the code uses PlatformSetting.get_solo().
    """

    list_display = (
        "id",
        "updated_at",
        "enable_music",
        "enable_podcast",
        "enable_book",
        "enable_video",
        "free_upload_minutes",
        "creator_daily_upload_limit",
        "playback_point_percent",
        "auto_approve_tracks",
    )

    fieldsets = (
        (
            "Content Types",
            {
                "fields": (
                    "enable_music",
                    "enable_podcast",
                    "enable_book",
                    "enable_audiobook",  # legacy
                    "enable_video",
                )
            },
        ),
        (
            "Upload Limits",
            {
                "fields": (
                    "free_upload_minutes",
                    "creator_daily_upload_limit",
                )
            },
        ),
        (
            "Moderation",
            {
                "fields": ("auto_approve_tracks",),
            },
        ),
        (
            "Points (Playback → Point)",
            {
                "fields": (
                    "playback_point_percent",
                    "play_award_percent",  # legacy
                )
            },
        ),
        (
            "Pricing (Price Per Point)",
            {
                "fields": (
                    "price_per_point_music",
                    "price_per_point_podcast",
                    "price_per_point_book",
                    "price_per_point_audiobook",  # legacy
                    "price_per_point_video",
                )
            },
        ),
    )
