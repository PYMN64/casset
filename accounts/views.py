import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
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
from .services import send_otp

UserModel = get_user_model()


class CassetLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm


def logout_view(request):
    logout(request)
    return redirect("login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("discover")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.get_or_create(user=user)
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
    return hashlib.sha256(f"{phone}:{code}".encode("utf-8")).hexdigest()


def _generate_username() -> str:
    token = secrets.token_urlsafe(9).replace("-", "").replace("_", "")
    return f"u-{token[:10]}"


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@login_required
def onboarding_view(request):
    from core.models import PlatformSetting

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    platform = PlatformSetting.get_solo()

    if request.method == "POST":
        form = OnboardingForm(request.POST, instance=profile, platform=platform)
        if form.is_valid():
            profile = form.save()
            action = request.POST.get("next_action") or "viewer"
            profile.role_intent = (
                UserProfile.RoleIntent.CREATOR if action == "creator" else UserProfile.RoleIntent.VIEWER
            )
            profile.save(update_fields=["role_intent"])
            messages.success(request, "Onboarding completed.")
            if action == "creator":
                return redirect("creator_apply")
            return redirect("discover")
        messages.error(request, "Please fix the errors and try again.")
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


def phone_start_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile and profile.phone_verified_at:
            return redirect("discover")

    form = PhoneStartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = _normalize_phone(form.cleaned_data["phone_number"])
        now = timezone.now()

        last = PhoneOTP.objects.filter(phone_number=phone).order_by("-created_at").first()
        if last and last.last_sent_at and (now - last.last_sent_at).total_seconds() < 60:
            messages.error(request, "Please wait before requesting another code.")
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

        send_otp(phone, code)
        if settings.DEBUG:
            messages.success(request, f"Dev OTP: {code}")
        else:
            messages.success(request, "Verification code sent.")
        return redirect(reverse("phone_verify") + f"?phone={phone}")

    return render(request, "accounts/phone_start.html", {"form": form})


def phone_verify_view(request):
    current_user = None
    if request.user.is_authenticated:
        current_user = request.user
        profile = getattr(request.user, "profile", None)
        if profile and profile.phone_verified_at:
            return redirect("discover")

    phone_q = _normalize_phone(request.GET.get("phone") or "")
    form = PhoneVerifyForm(request.POST or None, initial={"phone_number": phone_q})

    if request.method == "POST" and form.is_valid():
        phone = _normalize_phone(form.cleaned_data["phone_number"])
        code = (form.cleaned_data["code"] or "").strip()

        otp = PhoneOTP.objects.filter(phone_number=phone, is_used=False).order_by("-created_at").first()
        if not otp:
            messages.error(request, "No valid code found. Try again.")
            return render(request, "accounts/phone_verify.html", {"form": form})

        now = timezone.now()
        if otp.expires_at < now:
            messages.error(request, "Code expired. Request a new code.")
            return redirect("phone_start")

        if otp.attempts >= 5:
            messages.error(request, "Too many attempts. Request a new code.")
            return redirect("phone_start")

        if otp.code_hash != _hash_code(phone, code):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            messages.error(request, "Invalid code.")
            return render(request, "accounts/phone_verify.html", {"form": form})

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        profile = UserProfile.objects.filter(phone_number=phone).select_related("user").first()
        if current_user is not None:
            if profile and profile.user_id != current_user.id:
                messages.error(request, "This phone is already linked to another account.")
                return render(request, "accounts/phone_verify.html", {"form": form})
            user = current_user
            profile, _ = UserProfile.objects.get_or_create(user=user)
        else:
            if profile:
                user = profile.user
            else:
                username = _generate_username()
                while UserModel.objects.filter(username=username).exists():
                    username = _generate_username()
                user = UserModel.objects.create(username=username)
                user.set_unusable_password()
                user.save(update_fields=["password"])
                profile, _ = UserProfile.objects.get_or_create(user=user)

        profile.phone_number = phone
        profile.phone_verified_at = timezone.now()
        profile.save(update_fields=["phone_number", "phone_verified_at"])

        login(request, user)
        return redirect("onboarding")

    return render(request, "accounts/phone_verify.html", {"form": form})


def google_login_placeholder(request):
    if getattr(settings, "ENABLE_ALLAUTH", False):
        try:
            return redirect(reverse("socialaccount_login", args=["google"]))
        except NoReverseMatch:
            pass
    messages.info(request, "Google login is not configured yet.")
    return redirect("login")


@login_required
def creator_apply_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.creator_status == UserProfile.CreatorStatus.APPROVED:
        return redirect("creator_studio")

    if request.method == "POST":
        profile.creator_enabled = True
        profile.creator_status = UserProfile.CreatorStatus.PENDING
        profile.save(update_fields=["creator_enabled", "creator_status"])
        messages.success(request, "Your creator application has been submitted.")
        return redirect("creator_apply")

    return render(request, "accounts/creator_apply.html", {"profile": profile})


@login_required
def creator_studio_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.creator_status != UserProfile.CreatorStatus.APPROVED:
        return redirect("creator_apply")

    my_tracks = (
        Track.objects.filter(creator=request.user)
        .order_by("-created_at")
        .prefetch_related("genres")
    )[:100]

    from plays.models import PlayEvent
    from django.db.models.functions import TruncDate
    from django.db.models import Count, Sum

    since = timezone.now() - timedelta(days=30)
    daily = (
        PlayEvent.objects.filter(track__creator=request.user, created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(plays=Count("id"), points=Sum("point_awarded"))
        .order_by("day")
    )

    top_tracks = (
        Track.objects.filter(creator=request.user)
        .order_by("-play_count")[:5]
    )

    return render(
        request,
        "accounts/creator_studio.html",
        {
            "profile": profile,
            "tracks": my_tracks,
            "daily": list(daily),
            "top_tracks": top_tracks,
        },
    )


CREATOR_HANDLE_RESERVED = {
    "admin",
    "api",
    "static",
    "media",
    "accounts",
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
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.creator_status == UserProfile.CreatorStatus.NONE and not profile.creator_enabled:
        return redirect("creator_apply")

    if request.method == "POST":
        form = CreatorHandleForm(request.POST, instance=profile, reserved=CREATOR_HANDLE_RESERVED)
        if form.is_valid():
            form.save()
            messages.success(request, "Your public handle has been set.")
            return redirect("creator_studio")
        messages.error(request, "Please fix the errors and try again.")
    else:
        form = CreatorHandleForm(instance=profile, reserved=CREATOR_HANDLE_RESERVED)

    return render(request, "accounts/creator_handle.html", {"profile": profile, "form": form})


def profile_legacy_redirect(request, username):
    return redirect("public_profile", username=username)


def public_profile(request, username):
    user_obj = get_object_or_404(UserModel, username=username)
    profile, _ = UserProfile.objects.get_or_create(user=user_obj)
    if profile.public_handle:
        return redirect("public_profile_by_handle", handle=profile.public_handle)

    tracks = Track.objects.filter(
        creator=user_obj,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    ).order_by("-created_at")[:50]

    total_plays = Track.objects.filter(creator=user_obj).aggregate(s=models.Sum("play_count"))["s"] or 0
    total_likes = user_obj.tracks.aggregate(s=models.Count("likes"))["s"] if hasattr(user_obj, "tracks") else 0
    followers_count = user_obj.followers.count() if hasattr(user_obj, "followers") else 0
    following_count = user_obj.following.count() if hasattr(user_obj, "following") else 0

    suggested = UserModel.objects.all().exclude(id=user_obj.id)
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
        },
    )


def public_profile_by_handle(request, handle):
    profile = get_object_or_404(UserProfile, public_handle__iexact=handle)
    user_obj = profile.user

    tracks = Track.objects.filter(
        creator=user_obj,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    ).order_by("-created_at")[:50]

    total_plays = Track.objects.filter(creator=user_obj).aggregate(s=models.Sum("play_count"))["s"] or 0
    total_likes = user_obj.tracks.aggregate(s=models.Count("likes"))["s"] if hasattr(user_obj, "tracks") else 0
    followers_count = user_obj.followers.count() if hasattr(user_obj, "followers") else 0
    following_count = user_obj.following.count() if hasattr(user_obj, "following") else 0

    suggested = UserModel.objects.all().exclude(id=user_obj.id)
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
            messages.success(request, "Profile updated.")
            return redirect("settings")
        messages.error(request, "Please fix the errors and try again.")
    else:
        form = ProfileSettingsForm(instance=profile)

    return render(request, "accounts/settings.html", {"form": form, "profile": profile})


@login_required
def dashboard_view(request):
    from datetime import date
    from django.db.models import Count
    from django.http import HttpResponse
    import csv

    from core.models import PlatformSetting
    from plays.models import PlayEvent

    try:
        range_days = int(request.GET.get("range", 30) or 30)
    except ValueError:
        range_days = 30
    if range_days not in (7, 30, 90, 180):
        range_days = 30
    since_date = date.today() - timedelta(days=range_days)

    platform = PlatformSetting.get_solo()

    rows = (
        PlayEvent.objects.filter(
            track__creator=request.user,
            point_awarded=True,
            created_at__date__gte=since_date,
        )
        .values("track__content_type")
        .annotate(points=Count("id"))
    )

    points_by_type = {r["track__content_type"] or "music": int(r["points"] or 0) for r in rows}
    book_points = points_by_type.pop("audiobook", 0) + points_by_type.pop("book", 0)
    if book_points:
        points_by_type["book"] = book_points

    revenue_by_type = {
        t: points_by_type.get(t, 0) * platform.price_per_point(t)
        for t in ["music", "podcast", "book", "video"]
    }
    total_points = sum(points_by_type.values())
    total_revenue = sum(revenue_by_type.values())

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=dashboard.csv"
        writer = csv.writer(response)
        writer.writerow(["type", "points", "revenue"])
        for t in ["music", "podcast", "book", "video"]:
            writer.writerow([t, points_by_type.get(t, 0), revenue_by_type.get(t, 0)])
        writer.writerow(["total", total_points, total_revenue])
        return response

    return render(
        request,
        "accounts/dashboard.html",
        {
            "points_by_type": points_by_type,
            "revenue_by_type": revenue_by_type,
            "total_points": total_points,
            "total_revenue": total_revenue,
            "since": since_date.isoformat(),
            "platform": platform,
            "range_days": range_days,
        },
    )
