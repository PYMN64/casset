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

    class AuthProvider(models.TextChoices):
        """How this account was originally created.

        Not an authorisation decision — it exists so the UI can say
        "you signed up with Google" instead of showing a password-change
        form to an account that has no usable password.
        """

        PASSWORD = "password", "Password"
        PHONE = "phone", "Phone OTP"
        GOOGLE = "google", "Google"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)

    # MVP: URL ها (بعداً میشه FileField/S3)
    # avatar_url = models.URLField(blank=True)
    cover = models.ImageField(upload_to="accounts/covers/", null=True, blank=True)
    avatar = models.ImageField(upload_to="accounts/avatars/", null=True, blank=True)
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

    # Staff-only trust signal shown as a badge next to the creator's name —
    # deliberately independent of creator_status (approved just means "may
    # publish"; verified means "staff has confirmed this is who they claim
    # to be", e.g. a known artist). Toggled from core/staff_views.py.
    is_verified = models.BooleanField(default=False)

    # --- Moderation: account suspension ---
    # Enforcement is via the standard `User.is_active` flag (blocks password
    # login automatically; phone-OTP login checks it explicitly — see
    # accounts/views.py::phone_verify_view). These two fields are audit
    # metadata only, not the source of truth for "is this account blocked".
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.CharField(max_length=240, blank=True)

    # --- Identity provenance ---
    # Set once at sign-up. Google sign-in additionally stamps
    # email_verified_at, because Google has already proved the address.
    auth_provider = models.CharField(
        max_length=16, choices=AuthProvider.choices, default=AuthProvider.PASSWORD
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    google_sub = models.CharField(
        max_length=64, blank=True, null=True, unique=True,
        help_text="Google's stable subject id. Immutable per Google account, "
                  "unlike the email address — this is what we match on.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def public_name(self) -> str:
        return self.display_name.strip() or self.public_handle or self.user.username

    # ------------------------------------------------------------------
    # Publisher eligibility
    #
    # Product rule: choosing a public handle is what turns a listener into
    # a publisher — but a publisher must be reachable, so a verified phone
    # number is a hard prerequisite. Both conditions live here so views,
    # templates and the upload gate all read the same definition instead
    # of each re-deriving it.
    # ------------------------------------------------------------------

    @property
    def phone_verified(self) -> bool:
        return bool(self.phone_number and self.phone_verified_at)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def can_publish(self) -> bool:
        """May this account put content in front of the public?

        Deliberately does NOT gate uploading a draft — a draft is private
        and harmless. It gates submitting for review (uploads/views.py
        ::submit_track), which is the moment content becomes public-bound.
        """
        if self.creator_status == self.CreatorStatus.REJECTED:
            return False
        return bool(self.public_handle) and self.phone_verified

    def publish_blockers(self) -> list[str]:
        """Ordered list of what still stands between this account and
        publishing. Drives the checklist UI on the publisher page."""
        blockers = []
        if not self.phone_verified:
            blockers.append("phone")
        if not self.public_handle:
            blockers.append("handle")
        if self.creator_status == self.CreatorStatus.REJECTED:
            blockers.append("rejected")
        return blockers

    @property
    def profile_url(self) -> str:
        """Canonical public URL for this profile.

        Handle form (/name/) when one is set — that is the shareable
        identity; otherwise the /@username/ form, which always resolves.
        """
        from django.urls import reverse

        if self.public_handle:
            return reverse("public_profile_by_handle", kwargs={"handle": self.public_handle})
        return reverse("public_profile", kwargs={"username": self.user.username})

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
