from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import UserProfile
from core.models import PlatformSetting
from plays.models import PlayEvent
from .models import PayoutRequest


def _eligible_for_payout(profile: UserProfile) -> bool:
    if not getattr(profile, "creator_status", None):
        return False
    if profile.creator_status != UserProfile.CreatorStatus.APPROVED:
        return False

    setting = PlatformSetting.get_solo()
    since = timezone.now() - timedelta(days=30)
    plays = PlayEvent.objects.filter(track__creator=profile.user, created_at__gte=since).count()
    points = PlayEvent.objects.filter(
        track__creator=profile.user,
        point_awarded=True,
        created_at__gte=since,
    ).count()

    if int(setting.min_valid_plays_30d or 0) > 0 and plays < int(setting.min_valid_plays_30d):
        return False
    if int(setting.min_payout_points_30d or 0) > 0 and points < int(setting.min_payout_points_30d):
        return False

    return True


@login_required
def vip_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "billing/vip.html", {"profile": profile})


@login_required
def activate_vip_dev(request):
    if not settings.DEBUG:
        return redirect("vip")

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
    eligible = _eligible_for_payout(profile)
    return render(
        request,
        "billing/payout.html",
        {
            "profile": profile,
            "setting": setting,
            "payouts": payouts,
            "eligible": eligible,
        },
    )


@login_required
def create_payout_request(request):
    if request.method != "POST":
        return redirect("payout")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    setting = PlatformSetting.get_solo()
    if not _eligible_for_payout(profile):
        messages.error(request, "You are not eligible for payout yet.")
        return redirect("payout")

    try:
        amount = int(request.POST.get("amount") or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        messages.error(request, "Invalid amount.")
        return redirect("payout")

    min_amount = int(setting.min_payout_amount or 0)
    if min_amount > 0 and amount < min_amount:
        messages.error(request, f"Minimum payout is {min_amount}.")
        return redirect("payout")

    unit = max(1, int(setting.price_per_point_music or 1))
    max_amount = int(profile.points or 0) * unit
    if amount > max_amount:
        amount = max_amount

    if amount <= 0:
        messages.error(request, "No available balance.")
        return redirect("payout")

    PayoutRequest.objects.create(user=request.user, amount=amount)
    messages.success(request, "Payout request submitted.")
    return redirect("payout")
