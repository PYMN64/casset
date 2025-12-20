from django.conf import settings
from django.db import models


class PlayEvent(models.Model):
    track = models.ForeignKey("tracks.Track", on_delete=models.CASCADE, related_name="play_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_hash = models.CharField(max_length=64)      # sha256 hex
    ua_hash = models.CharField(max_length=64, blank=True)  # sha256 hex (optional)
    day_key = models.CharField(max_length=10)      # YYYY-MM-DD
    created_at = models.DateTimeField(auto_now_add=True)
    point_awarded = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["track", "day_key"]),
            models.Index(fields=["ip_hash", "day_key"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["track", "ip_hash", "day_key"], name="uniq_play_track_ip_day")
        ]

    def __str__(self):
        return f"PlayEvent(track={self.track_id}, day={self.day_key})"


class DailyTrackStat(models.Model):
    """Pre-aggregated daily stats for fast dashboards.

    This table is computed from PlayEvent (via a management command / cron).
    It allows fast charts without scanning raw events.
    """

    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="daily_stats"
    )
    day = models.DateField()
    plays = models.PositiveIntegerField(default=0)
    unique_plays = models.PositiveIntegerField(default=0)
    points_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["track", "day"], name="uniq_daily_track_day"
            )
        ]
        indexes = [
            models.Index(fields=["track", "day"], name="plays_dts_track_day"),
            models.Index(fields=["day"], name="plays_dts_day"),
        ]
        ordering = ["-day"]

    def __str__(self) -> str:
        return f"DailyTrackStat(track={self.track_id}, day={self.day})"


class FraudFlag(models.Model):
    """Soft signals for suspicious behaviour.

    For MVP we only log and expose this to staff. No auto-ban.
    """

    class FlagType(models.TextChoices):
        PLAY_BURST = "play_burst", "Play burst"
        REPEATED_IP = "repeated_ip", "Repeated IP"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    track = models.ForeignKey("tracks.Track", on_delete=models.CASCADE, related_name="fraud_flags", null=True, blank=True)
    flag_type = models.CharField(max_length=32, choices=FlagType.choices)
    score = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['flag_type','created_at'])]
