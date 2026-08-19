from __future__ import annotations

from django.db import models


class PlatformSetting(models.Model):
    """Singleton-like platform settings editable in admin.

    Keep exactly one row. New fields are additive to keep migrations stable.
    """

    # Upload availability (legacy names)
    enable_music = models.BooleanField(default=True)
    enable_podcast = models.BooleanField(default=True)
    enable_audiobook = models.BooleanField(default=False)
    enable_video = models.BooleanField(default=False)

    # V3 friendly alias for audiobook -> book (additive)
    enable_book = models.BooleanField(default=False)

    # Upload limits
    free_upload_minutes = models.PositiveIntegerField(default=180)
    creator_daily_upload_limit = models.PositiveIntegerField(default=20)

    # Moderation
    auto_approve_tracks = models.BooleanField(
        default=False,
        help_text=(
            "اگر فعال باشد، محتوای ارسالی کاربران بدون بررسی دستی staff فوراً "
            "تایید و منتشر می‌شود (صف بررسی ترک دور زده می‌شود). برای شروع سریع‌تر "
            "و کاهش اصطکاک مناسب است؛ گزارش‌دهی کاربران (Report) کماکان فعال می‌ماند."
        ),
    )

    # Points awarding threshold
    # Legacy (0.0 - 1.0)
    play_award_percent = models.FloatField(default=0.60)
    # V3 preferred (0 - 100)
    playback_point_percent = models.PositiveIntegerField(
        default=60,
        help_text="Percent of playback required to award 1 point (e.g. 60)",
    )

    # Price per point by content type (legacy names)
    price_per_point_music = models.PositiveIntegerField(default=0)
    price_per_point_podcast = models.PositiveIntegerField(default=0)
    price_per_point_audiobook = models.PositiveIntegerField(default=0)
    price_per_point_video = models.PositiveIntegerField(default=0)

    # V3 alias for book
    price_per_point_book = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls) -> PlatformSetting:
        obj = cls.objects.order_by("id").first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def playback_threshold_ratio(self) -> float:
        """Return the points threshold as a ratio (0..1).

        We prefer `playback_point_percent` but keep fallback to legacy field.
        """
        try:
            pct = int(self.playback_point_percent or 0)
            pct = max(0, min(100, pct))
            if pct > 0:
                return pct / 100.0
        except Exception:
            pass
        # Legacy fallback
        return float(self.play_award_percent or 0.60)

    def price_per_point(self, content_type: str) -> int:
        """Return configured price per point for a given content type."""
        content_type = (content_type or "").lower()
        if content_type == "book":
            return int(self.price_per_point_book or self.price_per_point_audiobook or 0)
        return {
            "music": int(self.price_per_point_music or 0),
            "podcast": int(self.price_per_point_podcast or 0),
            "audiobook": int(self.price_per_point_audiobook or 0),
            "video": int(self.price_per_point_video or 0),
        }.get(content_type, 0)

    def is_content_type_enabled(self, content_type: str) -> bool:
        content_type = (content_type or "").lower()
        if content_type == "book":
            return bool(self.enable_book or self.enable_audiobook)
        return {
            "music": bool(self.enable_music),
            "podcast": bool(self.enable_podcast),
            "audiobook": bool(self.enable_audiobook),
            "video": bool(self.enable_video),
        }.get(content_type, True)

    class Meta:
        verbose_name = "Platform setting"
        verbose_name_plural = "Platform settings"

    def __str__(self):
        return f"PlatformSetting#{self.pk}"
