from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta

from accounts.models import UserProfile
from .models import PayoutRequest
from core.models import PlatformSetting


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
    return render(request, "billing/vip.html", {"profile": profile})


@login_required
def activate_vip_dev(request):
    # فقط برای DEV: 30 روز VIP فعال می‌کنه
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.vip_until = timezone.now() + timedelta(days=30)
    profile.is_vip = True
    profile.save()
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

    PayoutRequest.objects.create(user=request.user, amount=amount)
    return redirect("payout")
