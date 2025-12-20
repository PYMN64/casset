from django.db import models


class FeaturedPin(models.Model):
    """Admin-controlled pins for the Discover page.

    Simple by design: pin a Track in a chosen position.
    - is_active: quick on/off
    - starts_at/ends_at: optional scheduling
    """

    track = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        related_name="featured_pins",
    )
    position = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "position"], name="exp_pin_active_pos"),
        ]

    def __str__(self) -> str:
        return f"Pin#{self.pk} track={self.track_id} pos={self.position}"
