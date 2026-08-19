from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.eligibility import compute_eligibility
from accounts.models import UserProfile

from .models import Plan, Subscription


@login_required
def vip_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    plans = Plan.objects.filter(is_active=True).order_by("id")
    active_sub = Subscription.objects.filter(user=request.user, status="active").order_by("-created_at").first()

    elig = compute_eligibility(request.user)

    return render(request, "subscriptions/vip.html", {
        "profile": profile,
        "plans": plans,
        "active_sub": active_sub,
        "elig": elig,
    })


@login_required
def activate_vip_dev(request):
    # فقط برای توسعه (DEV)
    if not settings.DEBUG:
        return redirect("vip_page")

    plan, _ = Plan.objects.get_or_create(
        code="vip_monthly",
        defaults={"name": "VIP Monthly", "price_display": "Dev"}
    )
    Subscription.objects.create(
        user=request.user,
        plan=plan,
        status="active",
        ends_at=timezone.now() + timedelta(days=30),
    )
    return redirect("vip_page")
