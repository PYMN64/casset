from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    class PrimaryContentType(models.TextChoices):
        MUSIC = "music", "Music"
        PODCAST = "podcast", "Podcast"
        AUDIOBOOK = "audiobook", "Audiobook"
        VIDEO = "video", "Video"

    class CreatorStatus(models.TextChoices):
        NONE = "none", "None"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class RoleIntent(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        CREATOR = "creator", "Creator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)

    cover = models.ImageField(upload_to="covers/", null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    points = models.IntegerField(default=0)
    follower_count = models.PositiveIntegerField(default=0)

    primary_content_type = models.CharField(
        max_length=16,
        choices=PrimaryContentType.choices,
        default=PrimaryContentType.MUSIC,
    )

    is_vip = models.BooleanField(default=False)
    vip_until = models.DateTimeField(null=True, blank=True)

    def has_vip(self) -> bool:
        if self.is_vip:
            return True
        if self.vip_until and self.vip_until > timezone.now():
            return True

        try:
            from billing.models import Invoice

            if Invoice.objects.filter(
                user=self.user,
                status=Invoice.Status.PAID,
            ).exclude(valid_until__isnull=False, valid_until__lte=timezone.now()).exists():
                return True
        except Exception:
            pass

        try:
            from subscriptions.models import Subscription

            return Subscription.objects.filter(user=self.user, status="active").exclude(
                ends_at__isnull=False, ends_at__lte=timezone.now()
            ).exists()
        except Exception:
            return False

    website_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)

    public_handle = models.SlugField(max_length=30, unique=True, null=True, blank=True)
    public_handle_set_at = models.DateTimeField(null=True, blank=True)

    phone_number = models.CharField(max_length=32, blank=True, null=True, unique=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    onboarding_complete = models.BooleanField(default=False)

    interests = models.JSONField(default=list, blank=True)
    role_intent = models.CharField(
        max_length=16,
        choices=RoleIntent.choices,
        default=RoleIntent.VIEWER,
    )

    creator_enabled = models.BooleanField(default=False)
    creator_status = models.CharField(
        max_length=16, choices=CreatorStatus.choices, default=CreatorStatus.NONE
    )

    # KYC placeholders (not active yet)
    legal_full_name = models.CharField(max_length=120, blank=True)
    national_id = models.CharField(max_length=32, blank=True)
    bank_iban = models.CharField(max_length=40, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def public_name(self) -> str:
        return self.display_name.strip() or self.user.username

    def __str__(self):
        return f"Profile({self.user.username})"


class PhoneOTP(models.Model):
    """One-time code for phone-based sign-in."""

    phone_number = models.CharField(max_length=32, db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "created_at"]),
            models.Index(fields=["phone_number", "is_used"]),
        ]

    def __str__(self) -> str:
        return f"PhoneOTP({self.phone_number}, used={self.is_used})"
