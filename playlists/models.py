from django.conf import settings
from django.db import models


class Playlist(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="playlists")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "created_at"])]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="items")
    track = models.ForeignKey("tracks.Track", on_delete=models.CASCADE, related_name="in_playlists")
    # Manual sort position (lowest first). New items append past the current
    # max — see api_playlist_toggle_track — so existing rows built before
    # this field existed (default=0) simply sort first, oldest-first via the
    # created_at tiebreaker below, which is a harmless one-time ordering.
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["playlist", "track"], name="uniq_playlist_track")
        ]
        indexes = [models.Index(fields=["playlist", "created_at"])]

    def __str__(self):
        return f"{self.playlist_id} -> {self.track_id}"
