import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from tracks.models import Track

from .forms import (
    CreatorHandleForm,
    LoginForm,
    OnboardingForm,
    PhoneStartForm,
    PhoneVerifyForm,
    ProfileSettingsForm,
    RegisterForm,
)
from .models import PhoneOTP, UserProfile

UserModel = get_user_model()


class CassetLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm


def logout_view(request):
    """Log out the user.

    Django's built-in LogoutView may require POST depending on version.
    For this project (consumer product UX), we support GET logout and
    then redirect to login.
    """
    logout(request)
    return redirect("login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("discover")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("onboarding")

    return render(request, "accounts/register.html", {"form": form})


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip().replace(" ", "")
    if p.startswith("+98"):
        p = "0" + p[3:]
    if p.startswith("98") and len(p) >= 12:
        p = "0" + p[2:]
    return p


def _hash_code(phone: str, code: str) -> str:
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _generate_username() -> str:
    # Never derive from phone; keep it unguessable.
    token = secrets.token_urlsafe(9).replace("-", "").replace("_", "")
    return f"u-{token[:10]}"


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _rate_limited(request, bucket: str, *, limit: int, window_seconds: int) -> bool:
    """Return True if this IP has exceeded `limit` requests to `bucket`
    within `window_seconds`. Same cache-counter pattern as plays/views.py
    and explore/views.py's own `_rate_limited`.

    This is a second, IP-level layer on top of PhoneOTP's per-code attempt
    cap (5 tries per OTP row) — that cap alone doesn't stop an attacker
    from requesting/guessing codes across many different phone numbers
    from one IP.
    """
    from django.core.cache import cache

    ip = _get_ip(request) or "unknown"
    key = f"rl:{bucket}:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    cur = cache.get(key, 0)
    if cur >= limit:
        return True
    cache.set(key, cur + 1, timeout=window_seconds)
    return False


def phone_start_view(request):
    """Start phone OTP login."""
    if request.user.is_authenticated:
        return redirect("discover")

    form = PhoneStartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_start", limit=10, window_seconds=600):
            messages.error(request, "درخواست‌های زیادی از این آدرس ارسال شده. کمی صبر کن.")
            return render(request, "accounts/phone_start.html", {"form": form})

        phone = _normalize_phone(form.cleaned_data["phone_number"])
        now = timezone.now()

        last = PhoneOTP.objects.filter(phone_number=phone).order_by("-created_at").first()
        if last and last.last_sent_at and (now - last.last_sent_at).total_seconds() < 60:
            messages.error(request, "لطفاً کمی صبر کن و دوباره تلاش کن.")
            return render(request, "accounts/phone_start.html", {"form": form})

        code = f"{secrets.randbelow(1000000):06d}"
        PhoneOTP.objects.create(
            phone_number=phone,
            code_hash=_hash_code(phone, code),
            expires_at=now + timedelta(minutes=2),
            last_sent_at=now,
            ip_address=_get_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:256],
        )

        # TODO: integrate SMS provider.
        # SECURITY: only show code in DEBUG mode — never in production.
        if settings.DEBUG:
            messages.success(request, f"[DEV] کد تست: {code}")
        else:
            messages.success(request, "کد ورود به شماره شما ارسال شد.")
        return redirect(reverse("phone_verify") + f"?phone={phone}")

    return render(request, "accounts/phone_start.html", {"form": form})


def phone_verify_view(request):
    """Verify OTP and log in / create user."""
    if request.user.is_authenticated:
        return redirect("discover")

    phone_q = _normalize_phone(request.GET.get("phone") or "")
    form = PhoneVerifyForm(request.POST or None, initial={"phone_number": phone_q})

    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_verify", limit=15, window_seconds=600):
            messages.error(request, "تلاش‌های زیادی از این آدرس ثبت شده. کمی صبر کن.")
            return render(request, "accounts/phone_verify.html", {"form": form})

        phone = _normalize_phone(form.cleaned_data["phone_number"])
        code = (form.cleaned_data["code"] or "").strip()

        otp = PhoneOTP.objects.filter(phone_number=phone, is_used=False).order_by("-created_at").first()
        if not otp:
            messages.error(request, "کد معتبر نیست یا منقضی شده.")
            return render(request, "accounts/phone_verify.html", {"form": form})

        now = timezone.now()
        if otp.expires_at < now:
            messages.error(request, "کد منقضی شده. دوباره درخواست بده.")
            return redirect("phone_start")

        if otp.attempts >= 5:
            messages.error(request, "تعداد تلاش‌ها بیش از حد مجاز است. دوباره درخواست بده.")
            return redirect("phone_start")

        if otp.code_hash != _hash_code(phone, code):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            messages.error(request, "کد اشتباه است.")
            return render(request, "accounts/phone_verify.html", {"form": form})

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        profile = UserProfile.objects.filter(phone_number=phone).select_related("user").first()
        if profile:
            user = profile.user
            if not user.is_active:
                # django.contrib.auth.login() does NOT check is_active on its
                # own (unlike ModelBackend.authenticate for password login) —
                # without this explicit check, a suspended account could log
                # back in through OTP, the only passwordless entry point.
                messages.error(request, "این حساب تعلیق شده است.")
                return redirect("phone_start")
        else:
            username = _generate_username()
            while User.objects.filter(username=username).exists():
                username = _generate_username()
            user = User.objects.create(username=username)
            user.set_unusable_password()
            user.save(update_fields=["password"])
            profile = user.profile

        profile.phone_number = phone
        profile.phone_verified_at = timezone.now()
        profile.save(update_fields=["phone_number", "phone_verified_at"])

        login(request, user)
        return redirect("onboarding")

    return render(request, "accounts/phone_verify.html", {"form": form})


def google_login_placeholder(request):
    """Placeholder endpoint for Google OAuth.

    When django-allauth is installed/configured, point this to the provider login.
    """
    messages.info(request, "ورود با گوگل به‌زودی فعال می‌شود.")
    return redirect("login")


@login_required
def onboarding_view(request):
    from core.models import PlatformSetting

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    platform = PlatformSetting.get_solo()

    if request.method == "POST":
        form = OnboardingForm(request.POST, instance=profile, platform=platform)
        if form.is_valid():
            form.save()
            action = request.POST.get("next_action") or "viewer"
            messages.success(request, "پروفایل شما ذخیره شد ✅")
            if action == "creator":
                return redirect("creator_apply")
            return redirect("discover")
        messages.error(request, "خطا: لطفاً موارد را بررسی کن.")
    else:
        form = OnboardingForm(instance=profile, platform=platform)

    return render(
        request,
        "accounts/onboarding.html",
        {
            "form": form,
            "platform": platform,
            "disabled_interest_types": getattr(form, "disabled_interest_types", set()),
            "selected_interests": form["interests"].value() or [],
        },
    )


@login_required
def creator_apply_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.creator_status == UserProfile.CreatorStatus.APPROVED:
        return redirect("creator_studio")

    if request.method == "POST":
        profile.creator_enabled = True
        profile.creator_status = UserProfile.CreatorStatus.PENDING
        profile.save(update_fields=["creator_enabled", "creator_status"])
        messages.success(request, "درخواست شما ثبت شد و در صف بررسی قرار گرفت ✅")
        return redirect("creator_apply")

    return render(request, "accounts/creator_apply.html", {"profile": profile})


@login_required
def creator_studio_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Content management
    my_tracks = (
        Track.objects.filter(creator=request.user)
        .order_by("-created_at")
        .prefetch_related("genres")
    )[:50]

    # Analytics (last 30 days)
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    from plays.models import PlayEvent

    since = timezone.now() - timedelta(days=30)
    daily = (
        PlayEvent.objects.filter(track__creator=request.user, created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(plays=Count("id"), points=Sum("point_awarded"))
        .order_by("day")
    )

    return render(
        request,
        "accounts/creator_studio.html",
        {
            "profile": profile,
            "tracks": my_tracks,
            "daily": list(daily),
        },
    )


CREATOR_HANDLE_RESERVED = {
    # core
    "admin",
    "api",
    "static",
    "media",
    # app routes
    "login",
    "logout",
    "register",
    "signup",
    "settings",
    "dashboard",
    "onboarding",
    "phone",
    "discover",
    "search",
    "upload",
    "uploads",
    "tracks",
    "track",
    "play",
    "plays",
    "playlist",
    "playlists",
    "billing",
    "subscriptions",
    "moderation",
    "explore",
}


@login_required
def creator_handle_view(request):
    """Allow creators to pick a public handle for shareable URL: /<handle>/"""

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.creator_status == UserProfile.CreatorStatus.NONE and not profile.creator_enabled:
        # Not a creator yet → send to apply page
        return redirect("creator_apply")

    if request.method == "POST":
        form = CreatorHandleForm(request.POST, instance=profile, reserved=CREATOR_HANDLE_RESERVED)
        if form.is_valid():
            form.save()
            messages.success(request, "یوزرنیم عمومی شما ذخیره شد ✅")
            return redirect("creator_studio")
        messages.error(request, "خطا: لطفاً یک یوزرنیم معتبر انتخاب کن.")
    else:
        form = CreatorHandleForm(instance=profile, reserved=CREATOR_HANDLE_RESERVED)

    return render(request, "accounts/creator_handle.html", {"profile": profile, "form": form})


def profile_legacy_redirect(request, username):
    return redirect("public_profile", username=username)


def public_profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile, _ = UserProfile.objects.get_or_create(user=user_obj)

    # Canonical URL: if creator has a public handle, always redirect to /<handle>/
    # to avoid duplicate profile pages for the same person.
    if profile.public_handle:
        return redirect("public_profile_by_handle", handle=profile.public_handle)

    tracks = Track.objects.filter(
        creator=user_obj,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    ).order_by("-created_at")[:50]

    total_plays = Track.objects.filter(creator=user_obj).aggregate(
        s=models.Sum("play_count")
    )["s"] or 0
    total_likes = user_obj.tracks.aggregate(s=models.Count("likes"))["s"] or 0
    followers_count = user_obj.followers.count() if hasattr(user_obj, "followers") else 0
    following_count = user_obj.following.count() if hasattr(user_obj, "following") else 0

    suggested = User.objects.all().exclude(id=user_obj.id)
    if request.user.is_authenticated and hasattr(request.user, "following"):
        suggested = suggested.exclude(
            id__in=request.user.following.values_list("creator_id", flat=True)
        )
    suggested = suggested.order_by("-id")[:6]

    return render(
        request,
        "accounts/public_profile_pro.html",
        {
            "user_obj": user_obj,
            "profile": profile,
            "tracks": tracks,
            "stats": {
                "plays": total_plays,
                "likes": total_likes,
                "followers": followers_count,
                "following": following_count,
            },
            "suggested_creators": suggested,
        },
    )


def public_profile_by_handle(request, handle):
    """Public profile reachable by /<handle>/ for creators."""
    profile = get_object_or_404(UserProfile, public_handle__iexact=handle)
    user_obj = profile.user

    tracks = Track.objects.filter(creator=user_obj, status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC).order_by("-created_at")[:50]

    total_plays = Track.objects.filter(creator=user_obj).aggregate(s=models.Sum("play_count"))["s"] or 0
    total_likes = user_obj.tracks.aggregate(s=models.Count("likes"))["s"] if hasattr(user_obj, "tracks") else 0
    followers_count = user_obj.followers.count() if hasattr(user_obj, "followers") else 0
    following_count = user_obj.following.count() if hasattr(user_obj, "following") else 0

    suggested = User.objects.all().exclude(id=user_obj.id)
    if request.user.is_authenticated and hasattr(request.user, "following"):
        suggested = suggested.exclude(id__in=request.user.following.values_list("creator_id", flat=True))
    suggested = suggested.order_by("-id")[:6]

    template = "accounts/public_profile_pro.html"
    return render(
        request,
        template,
        {
            "user_obj": user_obj,
            "profile": profile,
            "tracks": tracks,
            "stats": {
                "plays": total_plays,
                "likes": total_likes,
                "followers": followers_count,
                "following": following_count,
            },
            "suggested_creators": suggested,
            "canonical_handle": True,
        },
    )


@login_required
def settings_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileSettingsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "تنظیمات پروفایل ذخیره شد ✅")
            return redirect("settings")
        messages.error(request, "خطا: لطفاً موارد را بررسی کن.")
    else:
        form = ProfileSettingsForm(instance=profile)

    return render(request, "accounts/settings.html", {"form": form, "profile": profile})


@login_required
def dashboard_view(request):
    """User dashboard: points → revenue summary.

    Points are read from PointLedger (source of truth), not from
    PlayEvent.point_awarded which is an implementation detail of
    the play-gating system.
    """
    from datetime import date

    from django.db.models import Sum

    from core.models import PlatformSetting
    from plays.models import PointLedger

    since = (date.today() - timedelta(days=30)).isoformat()
    platform = PlatformSetting.get_solo()

    # Sum delta from Ledger for this creator's tracks in the last 30 days
    rows = (
        PointLedger.objects.filter(
            user=request.user,
            reason=PointLedger.Reason.PLAY_REWARD,
            created_at__date__gte=since,
        )
        .values("play_event__track__content_type")
        .annotate(points=Sum("delta"))
    )

    points_by_type = {
        r["play_event__track__content_type"] or "music": int(r["points"] or 0)
        for r in rows
    }
    book_points = points_by_type.pop("audiobook", 0) + points_by_type.pop("book", 0)
    if book_points:
        points_by_type["book"] = book_points

    revenue_by_type = {
        t: points_by_type.get(t, 0) * platform.price_per_point(t)
        for t in ["music", "podcast", "book", "video"]
    }
    total_points = sum(points_by_type.values())
    total_revenue = sum(revenue_by_type.values())

    return render(
        request,
        "accounts/dashboard.html",
        {
            "points_by_type": points_by_type,
            "revenue_by_type": revenue_by_type,
            "total_points": total_points,
            "total_revenue": total_revenue,
            "since": since,
            "platform": platform,
        },
    )
