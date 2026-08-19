from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User



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

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)

    # MVP: URL ها (بعداً میشه FileField/S3)
    # avatar_url = models.URLField(blank=True)
    cover = models.ImageField(upload_to="covers/", null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    points = models.IntegerField(default=0)
    follower_count = models.PositiveIntegerField(default=0)

    # Each user must pick a primary content type for their creator identity.
    # (Used for UI defaults and future recommendations.)
    primary_content_type = models.CharField(
        max_length=16,
        choices=PrimaryContentType.choices,
        default=PrimaryContentType.MUSIC,
    )

    is_vip = models.BooleanField(default=False)
    vip_until = models.DateTimeField(null=True, blank=True)

    def has_vip(self):
        """Return whether this user currently has active VIP access.

        Source of truth (in priority order):
        1. Fast-path cache fields `is_vip` / `vip_until` — for cheap
           checks in hot paths (templates, middleware). These are only
           valid while kept in sync; prefer the Invoice check below for
           accuracy after payment events.
        2. A paid, still-valid `billing.Invoice` — the canonical,
           re-derivable source of truth. `billing` is the single
           authoritative app for VIP/plan state; there is no other.
        """
        # 1) Fast path via profile flags
        if self.is_vip:
            return True
        if self.vip_until and self.vip_until > timezone.now():
            return True

        # 2) Canonical check: paid invoice with future valid_until
        from billing.models import Invoice

        return Invoice.objects.filter(
            user=self.user,
            status=Invoice.Status.PAID,
        ).exclude(valid_until__isnull=False, valid_until__lte=timezone.now()).exists()

    website_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)

    # Public creator handle used for profile URL: /<handle>/
    # Keep the system username (u-xxxx...) for authentication and internal references.
    public_handle = models.SlugField(max_length=30, unique=True, null=True, blank=True)
    public_handle_set_at = models.DateTimeField(null=True, blank=True)

    # --- Auth + Onboarding ---
    # For Iran-first UX we support phone OTP sign-in.
    # Keep phone on profile for easier querying without swapping AUTH_USER_MODEL.
    phone_number = models.CharField(max_length=32, blank=True, null=True, unique=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    onboarding_complete = models.BooleanField(default=False)

    # Multiple interests for recommendations. Store as a list of canonical keys.
    # Example: ["music","podcast"]
    interests = models.JSONField(default=list, blank=True)

    creator_enabled = models.BooleanField(default=False)
    creator_status = models.CharField(
        max_length=16, choices=CreatorStatus.choices, default=CreatorStatus.NONE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def public_name(self) -> str:
        return self.display_name.strip() or self.user.username

    def __str__(self):
        return f"Profile({self.user.username})"


class PhoneOTP(models.Model):
    """One-time code for phone-based sign-in.

    Notes:
    - Store only hash of the code.
    - Keep lightweight anti-abuse fields (attempts, last_sent_at, ip, user_agent).
    """

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
