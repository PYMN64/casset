
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.eligibility import compute_eligibility
from accounts.models import UserProfile
from core.models import PlatformSetting

from . import services
from .models import Invoice, PayoutRequest, Plan


def _eligible_for_payout(profile: UserProfile) -> bool:
    # Simple MVP eligibility: creator approved and has some points
    if not getattr(profile, "creator_status", None):
        return False
    if str(profile.creator_status) != "approved":
        return False
    return int(profile.points or 0) > 0


@login_required
def vip_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    plans = Plan.objects.filter(is_active=True)
    active_invoice = (
        Invoice.objects.filter(user=request.user, status=Invoice.Status.PAID)
        .order_by("-valid_until")
        .first()
    )
    elig = compute_eligibility(request.user)

    return render(request, "billing/vip.html", {
        "profile": profile,
        "plans": plans,
        "active_invoice": active_invoice,
        "elig": elig,
        "debug": settings.DEBUG,
    })


@login_required
def activate_vip_dev(request, plan_id: int | None = None):
    """DEV-ONLY helper to try the VIP flow without a real payment gateway.

    Unlike the previous implementation, this does NOT flip
    `UserProfile.is_vip` directly. It creates a real (paid) `Invoice`
    against a real `Plan`, so `UserProfile.has_vip()` derives VIP status
    from the same billing records a real payment would produce — matching
    the "counters/flags are derived, not hand-written" rule in
    CLAUDE.md's Constitution.
    """
    if not settings.DEBUG:
        # Never allow this outside local development.
        return redirect("vip")

    if plan_id:
        plan = get_object_or_404(Plan, id=plan_id, is_active=True)
    else:
        plan, _ = Plan.objects.get_or_create(
            code="vip_monthly",
            defaults={"title": "VIP Monthly", "price": 0, "duration_days": 30},
        )

    invoice = Invoice.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price,
        status=Invoice.Status.PENDING,
        provider="dev",
    )
    invoice.mark_paid()

    messages.success(request, f"VIP از طریق پلن «{plan.title}» فعال شد (Dev).")
    return redirect("vip")


@login_required
def start_payment(request, plan_id: int):
    """Real payment entry point — replaces activate_vip_dev in production.
    Redirects to whatever billing.services.get_payment_provider() resolves
    to (Zarinpal in prod, DevPaymentProvider in DEBUG without real
    credentials — see config/settings/prod.py for the fail-fast guard)."""
    plan = get_object_or_404(Plan, id=plan_id, is_active=True)
    callback_url = request.build_absolute_uri(reverse("payment_callback"))
    try:
        redirect_url = services.start_payment(user=request.user, plan=plan, callback_url=callback_url)
    except services.PaymentError:
        messages.error(request, "اتصال به درگاه پرداخت ناموفق بود. لطفاً دوباره تلاش کنید.")
        return redirect("vip")
    return redirect(redirect_url)


def payment_callback(request):
    """Gateway callback — verifies and finalizes the Invoice this Authority
    belongs to. Not @login_required: the gateway calls this directly, not
    the logged-in browser session (though in practice it's the same tab)."""
    invoice_id = request.GET.get("invoice_id")
    authority = request.GET.get("Authority")

    invoice = None
    if invoice_id:
        invoice = Invoice.objects.filter(pk=invoice_id).first()
    elif authority:
        invoice = Invoice.objects.filter(provider_ref=authority).first()
    if invoice is None:
        raise Http404("Invoice not found for this payment callback.")

    ok = services.complete_payment(invoice=invoice, callback_params=request.GET.dict())
    if ok:
        messages.success(request, f"VIP از طریق پلن «{invoice.plan.title}» فعال شد.")
    else:
        messages.error(request, "پرداخت تایید نشد یا ناموفق بود.")
    return redirect("vip")


@login_required
def payout_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    setting = PlatformSetting.get_solo()
    payouts = PayoutRequest.objects.filter(user=request.user).order_by("-created_at")[:20]
    return render(request, "billing/payout.html", {"profile": profile, "setting": setting, "payouts": payouts})


@login_required
def create_payout_request(request):
    if request.method != "POST":
        return redirect("payout")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _eligible_for_payout(profile):
        return redirect("payout")

    # An already-pending request must be resolved (paid/rejected) before a
    # new one can be filed — otherwise nothing stops a user from spamming
    # duplicate requests, each capped at their *full* point balance, which
    # would make outstanding-payout totals meaningless for staff review.
    if PayoutRequest.objects.filter(user=request.user, status=PayoutRequest.Status.PENDING).exists():
        messages.error(request, "شما در حال حاضر یک درخواست تسویه در حال بررسی دارید.")
        return redirect("payout")

    try:
        amount = int(request.POST.get("amount") or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        return redirect("payout")

    # MVP: allow request up to current earned value
    setting = PlatformSetting.get_solo()
    # Assume points are convertible at average price; for now, use music price as placeholder
    unit = max(1, int(setting.price_per_point_music or 1))
    max_amount = int(profile.points or 0) * unit
    if amount > max_amount:
        amount = max_amount

    # Lock in the exact point count backing this amount now — approve_payout
    # deducts *this* number later, not whatever amount/unit works out to at
    # approval time (price_per_point_music can change in between).
    points = amount // unit
    amount = points * unit

    PayoutRequest.objects.create(user=request.user, amount=amount, points=points)
    return redirect("payout")
