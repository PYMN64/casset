"""billing/services.py — payment gateway abstraction and payout decisions.

Payment provider pattern mirrors accounts/services.py's SMS provider: swap
providers via the PAYMENT_PROVIDER env var without touching call sites.
DevPaymentProvider (DEBUG-only) replaces the old activate_vip_dev shortcut
with something that still exercises the same Invoice/Transaction flow a
real gateway would. ZarinpalProvider talks to Zarinpal's real REST API —
see config/settings/prod.py for the fail-fast guard that keeps production
from booting with the dev provider or a missing merchant ID.

Payout approval is the other half of this module: approving a PayoutRequest
must deduct the creator's points through PointLedger (Constitution, CLAUDE.
md §2 — UserProfile.points is a derived cache, never hand-edited), the same
pattern plays/services.py uses for awarding them.
"""

import logging

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import UserProfile
from plays.models import PointLedger

from .models import Invoice, PayoutRequest, Transaction

logger = logging.getLogger("casset.billing")


class PaymentError(Exception):
    """Raised when a payment provider fails to create or verify a payment."""


# ---------------------------------------------------------------------------
# Payment provider abstraction
# ---------------------------------------------------------------------------

class PaymentProvider:
    def request_payment(self, *, invoice) -> str:
        """Create the payment on the gateway; return the URL to redirect to."""
        raise NotImplementedError

    def verify_payment(self, *, invoice, callback_params: dict) -> bool:
        """Verify a completed payment from callback params. True = paid."""
        raise NotImplementedError


class DevPaymentProvider(PaymentProvider):
    """DEBUG-only stand-in — no real gateway, no real money.

    Still creates a real Invoice/Transaction and redirects through the same
    callback view a real gateway would, so the request→callback→mark_paid
    path is exercised end-to-end even without Zarinpal credentials.
    """

    def request_payment(self, *, invoice) -> str:
        from django.urls import reverse

        invoice.provider = "dev"
        invoice.provider_ref = f"dev-{invoice.pk}"
        invoice.save(update_fields=["provider", "provider_ref"])
        return reverse("payment_callback") + f"?invoice_id={invoice.pk}&Status=OK&dev=1"

    def verify_payment(self, *, invoice, callback_params: dict) -> bool:
        return callback_params.get("Status") == "OK"


class ZarinpalProvider(PaymentProvider):
    """Real payment via Zarinpal (zarinpal.com) — the most widely used
    Iranian payment gateway, with well-documented REST API + Python SDK
    support. Amount is passed through as Invoice.amount unchanged (operators
    must ensure Plan.price is denominated the way their merchant account
    expects — Rial vs. Toman — Zarinpal's API itself doesn't disambiguate
    this at the request level without extra config this integration doesn't
    assume).
    """

    _REQUEST_PATH = "/pg/v4/payment/request.json"
    _VERIFY_PATH = "/pg/v4/payment/verify.json"
    _STARTPAY_PATH = "/pg/StartPay/{authority}"

    def __init__(self, *, merchant_id: str, callback_url: str, sandbox: bool = False):
        self.merchant_id = merchant_id
        self.callback_url = callback_url
        base = "https://sandbox.zarinpal.com" if sandbox else "https://api.zarinpal.com"
        pay_base = "https://sandbox.zarinpal.com" if sandbox else "https://www.zarinpal.com"
        self.request_url = base + self._REQUEST_PATH
        self.verify_url = base + self._VERIFY_PATH
        self.startpay_url = pay_base + self._STARTPAY_PATH

    def request_payment(self, *, invoice) -> str:
        payload = {
            "merchant_id": self.merchant_id,
            "amount": invoice.amount,
            "callback_url": self.callback_url,
            "description": f"Casset — {invoice.plan.title}",
        }
        data = self._post(self.request_url, payload)
        result = data.get("data") or {}
        if result.get("code") != 100:
            raise PaymentError(f"Zarinpal request failed: {data.get('errors') or result}")

        authority = result["authority"]
        invoice.provider = "zarinpal"
        invoice.provider_ref = authority
        invoice.save(update_fields=["provider", "provider_ref"])
        return self.startpay_url.format(authority=authority)

    def verify_payment(self, *, invoice, callback_params: dict) -> bool:
        if callback_params.get("Status") != "OK":
            return False
        payload = {
            "merchant_id": self.merchant_id,
            "amount": invoice.amount,
            "authority": invoice.provider_ref,
        }
        data = self._post(self.verify_url, payload)
        result = data.get("data") or {}
        # 100 = verified now; 101 = already verified earlier (still success —
        # a callback can legitimately be hit twice, e.g. user refresh).
        return result.get("code") in (100, 101)

    @staticmethod
    def _post(url: str, payload: dict) -> dict:
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("Zarinpal request to %s failed: %s", url, exc)
            raise PaymentError(str(exc)) from exc


def get_payment_provider(*, callback_url: str = "") -> PaymentProvider:
    provider = getattr(settings, "PAYMENT_PROVIDER", "dev")
    if provider == "zarinpal":
        return ZarinpalProvider(
            merchant_id=settings.ZARINPAL_MERCHANT_ID,
            callback_url=callback_url,
            sandbox=getattr(settings, "ZARINPAL_SANDBOX", False),
        )
    return DevPaymentProvider()


# ---------------------------------------------------------------------------
# Payment flow — Invoice/Transaction stay the single source of truth
# (provider/provider_ref already existed on Invoice for exactly this).
# ---------------------------------------------------------------------------

def start_payment(*, user, plan, callback_url: str) -> str:
    """Create a PENDING Invoice and return the URL to send the user to."""
    invoice = Invoice.objects.create(
        user=user, plan=plan, amount=plan.price, status=Invoice.Status.PENDING,
    )
    provider = get_payment_provider(callback_url=callback_url)
    try:
        redirect_url = provider.request_payment(invoice=invoice)
    except PaymentError as exc:
        invoice.status = Invoice.Status.FAILED
        invoice.save(update_fields=["status"])
        Transaction.objects.create(
            invoice=invoice, kind=Transaction.Kind.CREATE,
            status=Transaction.Status.ERROR, raw_payload={"error": str(exc)},
        )
        raise

    Transaction.objects.create(
        invoice=invoice, kind=Transaction.Kind.CREATE,
        status=Transaction.Status.OK, raw_payload={"redirect_url": redirect_url},
    )
    return redirect_url


def complete_payment(*, invoice, callback_params: dict) -> bool:
    """Verify a callback and mark the invoice paid/failed accordingly."""
    if invoice.status == Invoice.Status.PAID:
        return True  # idempotent — a callback can be hit more than once

    provider = get_payment_provider()
    try:
        verified = provider.verify_payment(invoice=invoice, callback_params=callback_params)
    except PaymentError as exc:
        invoice.status = Invoice.Status.FAILED
        invoice.save(update_fields=["status"])
        Transaction.objects.create(
            invoice=invoice, kind=Transaction.Kind.VERIFY,
            status=Transaction.Status.ERROR, raw_payload={"error": str(exc)},
        )
        return False

    if verified:
        invoice.mark_paid()
        Transaction.objects.create(
            invoice=invoice, kind=Transaction.Kind.VERIFY,
            status=Transaction.Status.OK, raw_payload=dict(callback_params),
        )
        return True

    invoice.status = Invoice.Status.FAILED
    invoice.save(update_fields=["status"])
    Transaction.objects.create(
        invoice=invoice, kind=Transaction.Kind.VERIFY,
        status=Transaction.Status.ERROR, raw_payload=dict(callback_params),
    )
    return False


# ---------------------------------------------------------------------------
# Payout approval — the missing PointLedger deduction (real bug found while
# building this: create_payout_request never reduced the creator's point
# balance, so an approved payout could be immediately requested again for
# the same points).
# ---------------------------------------------------------------------------

def approve_payout(*, payout: PayoutRequest, actor) -> bool:
    """Approve a pending payout: deduct points via PointLedger, mark paid.
    Idempotent — approving a non-pending payout is a no-op returning False."""
    if payout.status != PayoutRequest.Status.PENDING:
        return False

    with transaction.atomic():
        PointLedger.objects.create(
            user=payout.user,
            delta=-payout.points,
            reason=PointLedger.Reason.PAYOUT_DEDUCTION,
            note=f"Payout#{payout.pk} approved",
        )
        UserProfile.objects.filter(user=payout.user).update(points=F("points") - payout.points)
        payout.status = PayoutRequest.Status.PAID
        payout.paid_at = timezone.now()
        payout.save(update_fields=["status", "paid_at"])

    _audit_payout(payout=payout, actor=actor, action="approve_payout")
    logger.info("approve_payout: payout=%s user=%s points=%d", payout.pk, payout.user_id, payout.points)
    return True


def reject_payout(*, payout: PayoutRequest, actor, reason: str = "") -> bool:
    """Reject a pending payout — no point deduction. Idempotent."""
    if payout.status != PayoutRequest.Status.PENDING:
        return False

    payout.status = PayoutRequest.Status.REJECTED
    payout.admin_note = (reason or "").strip()[:500]
    payout.save(update_fields=["status", "admin_note"])

    _audit_payout(payout=payout, actor=actor, action="reject_payout", metadata={"reason": payout.admin_note})
    logger.info("reject_payout: payout=%s user=%s", payout.pk, payout.user_id)
    return True


def _audit_payout(*, payout, actor, action: str, metadata: dict | None = None) -> None:
    from moderation.models import AuditLog

    AuditLog.objects.create(
        actor=actor,
        target_type=AuditLog.TargetType.PAYOUT,
        payout=payout,
        target_user=payout.user,
        action=action,
        metadata={"amount": payout.amount, "points": payout.points, **(metadata or {})},
    )
