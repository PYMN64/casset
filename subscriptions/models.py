from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    code = models.CharField(max_length=40, unique=True)  # vip_monthly
    name = models.CharField(max_length=80)
    price_display = models.CharField(max_length=40, default="N/A")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        CANCELED = "canceled"
        EXPIRED = "expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["ends_at"]),
        ]

    def is_active_now(self):
        if self.status != self.Status.ACTIVE:
            return False
        if self.ends_at and self.ends_at <= timezone.now():
            return False
        return True
