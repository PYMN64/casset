from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Plan(models.Model):
    """VIP plans that can be sold.

    This is the single canonical Plan model for the platform. The old
    `subscriptions.Plan` (and its accompanying `Subscription` model) has
    been retired in favor of this one + `Invoice` (see CLAUDE.md issue #2).
    """

    code = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField(default=0)  # your currency unit
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.code or self.title, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.title} ({self.code})"


class Invoice(models.Model):
    """A purchase intent for a plan.

    `provider` + `provider_ref` are reserved for payment gateway integration.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="invoices")
    amount = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=40, blank=True)
    provider_ref = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"], name="billing_inv_user_status"),
            models.Index(fields=["valid_until"], name="billing_inv_valid_until"),
        ]
        ordering = ["-created_at"]

    def mark_paid(self):
        if self.status == self.Status.PAID:
            return
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.valid_until = self.paid_at + timezone.timedelta(days=int(self.plan.duration_days))
        self.save(update_fields=["status", "paid_at", "valid_until"])

    def __str__(self) -> str:
        return f"Invoice#{self.pk} {self.user_id} {self.status}"


class Transaction(models.Model):
    """Gateway interaction log (webhook-ready)."""

    class Kind(models.TextChoices):
        CREATE = "create", "Create"
        VERIFY = "verify", "Verify"
        WEBHOOK = "webhook", "Webhook"

    class Status(models.TextChoices):
        OK = "ok", "OK"
        ERROR = "error", "Error"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Tx#{self.pk} {self.kind} {self.status}"


class PayoutRequest(models.Model):
    """Monetization-ready payout request (no bank integration yet)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payouts")
    amount = models.PositiveIntegerField()
    # Points backing this payout, locked in at request time (not
    # re-derived from `amount` at approval time — price_per_point_music can
    # change between request and approval, and the deduction must match
    # exactly what the creator was quoted, not whatever the price is today).
    points = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"], name="billing_payout_user_status")]

    def __str__(self) -> str:
        return f"Payout#{self.pk} {self.user_id} {self.status}"
