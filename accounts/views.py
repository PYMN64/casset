import hashlib
import secrets  # noqa: F401  (kept importable: tests patch accounts.views.secrets.randbelow)
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
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from tracks.models import Track

from . import oauth
from .forms import (
    CreatorHandleForm,
    LoginForm,
    NotificationPreferenceForm,
    OnboardingForm,
    PhoneStartForm,
    PhoneVerifyForm,
    ProfileSettingsForm,
    RegisterForm,
)
from .models import PhoneOTP, UserProfile
from .services import (
    OTP_ERROR_MESSAGES,
    OTP_RESEND_COOLDOWN_SECONDS,
    attach_phone_to_user,
    issue_otp,
    normalize_phone,
    resolve_google_user,
    unique_username,
    verify_otp,
)

UserModel = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff and getattr(settings, "TRUST_PROXY_HEADERS", False):
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


def _safe_next(request, default: str = "") -> str:
    """Return ?next= only when it points back at this site.

    Without this check, `?next=https://evil.example` turns our own login
    page into an open redirect — the classic phishing primitive.
    """
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return default


def _seconds_until_resend(phone: str) -> int:
    """How long the user must still wait before another code can be sent.

    Surfaced in the UI as a live countdown instead of an unexplained
    "try again later" — the user can see the system is protecting the
    account rather than malfunctioning.
    """
    last = PhoneOTP.objects.filter(phone_number=phone).order_by("-created_at").first()
    if not (last and last.last_sent_at):
        return 0
    elapsed = (timezone.now() - last.last_sent_at).total_seconds()
    return max(0, int(OTP_RESEND_COOLDOWN_SECONDS - elapsed))


# ---------------------------------------------------------------------------
# Password auth
# ---------------------------------------------------------------------------

class CassetLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = False

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["google_enabled"] = oauth.is_configured()
        ctx["next"] = _safe_next(self.request)
        return ctx

    def form_valid(self, form):
        """Honour the "remember me" checkbox.

        Unchecked means the session cookie dies with the browser, which is
        what a user on a shared or public machine expects that box to
        control. Checked keeps Django's default SESSION_COOKIE_AGE.
        """
        response = super().form_valid(form)
        if not self.request.POST.get("remember_me"):
            self.request.session.set_expiry(0)
        return response


def logout_view(request):
    """Log the user out.

    POST only for the actual state change: a GET logout can be triggered by
    any third-party page embedding <img src="https://casset.ir/logout/">,
    which is a real (if low-severity) CSRF. A GET here just bounces the
    visitor home without touching the session.
    """
    if request.method != "POST":
        return redirect("discover")
    logout(request)
    messages.success(request, "از حساب خارج شدی. به امید دیدار!")
    return redirect("discover")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("discover")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.auth_provider = UserProfile.AuthProvider.PASSWORD
        profile.save(update_fields=["auth_provider"])
        login(request, user)
        return redirect("onboarding")

    return render(
        request,
        "accounts/register.html",
        {"form": form, "google_enabled": oauth.is_configured()},
    )


# ---------------------------------------------------------------------------
# Phone OTP — logged-out sign-in
# ---------------------------------------------------------------------------

def phone_start_view(request):
    """Start phone OTP login."""
    if request.user.is_authenticated:
        return redirect("discover")

    form = PhoneStartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_start", limit=10, window_seconds=600):
            messages.error(request, "درخواست‌های زیادی از این آدرس ارسال شده. کمی صبر کن.")
            return render(request, "accounts/phone_start.html", _phone_start_ctx(form))

        phone = normalize_phone(form.cleaned_data["phone_number"])
        ok, payload = issue_otp(
            phone,
            ip_address=_get_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT") or "",
        )
        if not ok:
            if payload == "cooldown":
                messages.error(request, "لطفاً کمی صبر کن و دوباره تلاش کن.")
            else:
                messages.error(request, OTP_ERROR_MESSAGES.get(payload, "خطا در ارسال کد."))
            return render(request, "accounts/phone_start.html", _phone_start_ctx(form))

        # SECURITY: only show code in DEBUG mode — never in production.
        if settings.DEBUG:
            messages.success(request, f"[DEV] کد تست: {payload}")
        else:
            messages.success(request, "کد ورود به شماره شما ارسال شد.")
        return redirect(reverse("phone_verify") + f"?phone={phone}")

    return render(request, "accounts/phone_start.html", _phone_start_ctx(form))


def _phone_start_ctx(form):
    return {"form": form, "google_enabled": oauth.is_configured()}


def phone_verify_view(request):
    """Verify OTP and log in / create user."""
    if request.user.is_authenticated:
        return redirect("discover")

    phone_q = normalize_phone(request.GET.get("phone") or request.POST.get("phone_number") or "")
    form = PhoneVerifyForm(request.POST or None, initial={"phone_number": phone_q})
    ctx = {"form": form, "phone": phone_q, "resend_in": _seconds_until_resend(phone_q)}

    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_verify", limit=15, window_seconds=600):
            messages.error(request, "تلاش‌های زیادی از این آدرس ثبت شده. کمی صبر کن.")
            return render(request, "accounts/phone_verify.html", ctx)

        phone = normalize_phone(form.cleaned_data["phone_number"])
        ok, err = verify_otp(phone, form.cleaned_data["code"])

        if not ok:
            if err in ("expired", "too_many_attempts"):
                messages.error(request, OTP_ERROR_MESSAGES[err])
                return redirect("phone_start")
            messages.error(request, OTP_ERROR_MESSAGES.get(err, "کد معتبر نیست."))
            return render(request, "accounts/phone_verify.html", ctx)

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
            user = User.objects.create(username=unique_username())
            user.set_unusable_password()
            user.save(update_fields=["password"])
            profile = user.profile
            profile.auth_provider = UserProfile.AuthProvider.PHONE
            profile.save(update_fields=["auth_provider"])

        profile.phone_number = phone
        profile.phone_verified_at = timezone.now()
        profile.save(update_fields=["phone_number", "phone_verified_at"])

        login(request, user)
        return redirect("onboarding")

    return render(request, "accounts/phone_verify.html", ctx)


# ---------------------------------------------------------------------------
# Phone OTP — attaching a number to an account that already exists
#
# This is what makes someone eligible to publish (UserProfile.can_publish).
# The logged-out flow above cannot serve it: there, a matching phone means
# "log into that account", which for a signed-in user would be an account
# swap, not a verification.
# ---------------------------------------------------------------------------

@login_required
def account_phone_start(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = PhoneStartForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_attach_start", limit=10, window_seconds=600):
            messages.error(request, OTP_ERROR_MESSAGES["rate_limited"])
            return render(request, "accounts/phone_add.html", {"form": form, "profile": profile})

        phone = normalize_phone(form.cleaned_data["phone_number"])

        taken = (
            UserProfile.objects.filter(phone_number=phone)
            .exclude(user_id=request.user.id)
            .exists()
        )
        if taken:
            messages.error(request, OTP_ERROR_MESSAGES["phone_taken"])
            return render(request, "accounts/phone_add.html", {"form": form, "profile": profile})

        ok, payload = issue_otp(
            phone,
            ip_address=_get_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT") or "",
        )
        if not ok:
            messages.error(request, OTP_ERROR_MESSAGES.get(payload, "خطا در ارسال کد."))
            return render(request, "accounts/phone_add.html", {"form": form, "profile": profile})

        if settings.DEBUG:
            messages.success(request, f"[DEV] کد تست: {payload}")
        else:
            messages.success(request, "کد تایید به شماره شما ارسال شد.")
        return redirect(reverse("account_phone_verify") + f"?phone={phone}")

    return render(request, "accounts/phone_add.html", {"form": form, "profile": profile})


@login_required
def account_phone_verify(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    phone_q = normalize_phone(request.GET.get("phone") or request.POST.get("phone_number") or "")
    form = PhoneVerifyForm(request.POST or None, initial={"phone_number": phone_q})
    ctx = {
        "form": form,
        "profile": profile,
        "phone": phone_q,
        "resend_in": _seconds_until_resend(phone_q),
        "attaching": True,
    }

    if request.method == "POST" and form.is_valid():
        if _rate_limited(request, "phone_attach_verify", limit=15, window_seconds=600):
            messages.error(request, OTP_ERROR_MESSAGES["rate_limited"])
            return render(request, "accounts/phone_verify.html", ctx)

        phone = normalize_phone(form.cleaned_data["phone_number"])
        ok, err = verify_otp(phone, form.cleaned_data["code"])
        if not ok:
            if err in ("expired", "too_many_attempts"):
                messages.error(request, OTP_ERROR_MESSAGES[err])
                return redirect("account_phone_start")
            messages.error(request, OTP_ERROR_MESSAGES.get(err, "کد معتبر نیست."))
            return render(request, "accounts/phone_verify.html", ctx)

        attached, err = attach_phone_to_user(request.user, phone)
        if not attached:
            messages.error(request, OTP_ERROR_MESSAGES.get(err, "خطا در ثبت شماره."))
            return redirect("account_phone_start")

        messages.success(request, "شماره موبایل شما تایید شد ✅")
        return redirect(_safe_next(request, reverse("creator_apply")))

    return render(request, "accounts/phone_verify.html", ctx)


# ---------------------------------------------------------------------------
# Google sign-in
# ---------------------------------------------------------------------------

def google_login_start(request):
    """Redirect to Google's consent screen."""
    if request.user.is_authenticated:
        return redirect("discover")
    if not oauth.is_configured():
        messages.info(request, "ورود با گوگل روی این سرور فعال نیست. با شماره موبایل وارد شو.")
        return redirect("login")

    redirect_uri = request.build_absolute_uri(reverse("google_callback"))
    url = oauth.build_authorization_url(
        request, redirect_uri=redirect_uri, next_url=_safe_next(request)
    )
    return redirect(url)


def google_callback(request):
    """Handle Google's redirect back to us."""
    if request.user.is_authenticated:
        return redirect("discover")

    if request.GET.get("error"):
        messages.error(request, "ورود با گوگل لغو شد.")
        return redirect("login")

    code = request.GET.get("code") or ""
    state = request.GET.get("state") or ""
    if not code:
        messages.error(request, "پاسخ نامعتبر از گوگل دریافت شد.")
        return redirect("login")

    try:
        identity = oauth.exchange_code(request, code=code, state=state)
    except oauth.GoogleAuthError as exc:
        messages.error(request, GOOGLE_ERROR_MESSAGES.get(str(exc), "ورود با گوگل ناموفق بود."))
        return redirect("login")

    user, created = resolve_google_user(identity)

    if not user.is_active:
        messages.error(request, "این حساب تعلیق شده است.")
        return redirect("login")

    login(request, user, backend="django.contrib.auth.backends.AllowAllUsersModelBackend")

    if created or not user.profile.onboarding_complete:
        return redirect("onboarding")
    messages.success(request, "خوش برگشتی 👋")
    return redirect(identity.get("next") or "discover")


GOOGLE_ERROR_MESSAGES = {
    "state_mismatch": "درخواست ورود معتبر نبود. دوباره تلاش کن.",
    "expired": "زمان ورود با گوگل تمام شد. دوباره تلاش کن.",
    "no_flow": "درخواست ورود پیدا نشد. دوباره از ابتدا تلاش کن.",
    "email_unverified": "ایمیل گوگل شما تایید نشده است. ابتدا آن را در گوگل تایید کن.",
    "network": "ارتباط با گوگل برقرار نشد. کمی بعد دوباره تلاش کن.",
}


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

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
            "nav_active": "onboarding",
        },
    )


# ---------------------------------------------------------------------------
# Becoming a publisher
# ---------------------------------------------------------------------------

@login_required
def creator_apply_view(request):
    """The publisher checklist.

    Product rule (and the reason this page exists at all): picking a public
    handle is what turns a listener into a publisher, and a publisher must
    have a verified phone number. Both are shown as an explicit checklist
    so the user always knows what is left, instead of hitting a wall later
    at submit-for-review time.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # Records intent even while the checklist is incomplete, so the
        # studio and staff console can tell "wants to publish" apart from
        # "never asked".
        if profile.creator_status != UserProfile.CreatorStatus.REJECTED:
            profile.creator_enabled = True
            if profile.can_publish:
                profile.creator_status = UserProfile.CreatorStatus.APPROVED
            elif profile.creator_status == UserProfile.CreatorStatus.NONE:
                profile.creator_status = UserProfile.CreatorStatus.PENDING
            profile.save(update_fields=["creator_enabled", "creator_status"])
            messages.success(request, "درخواست شما ثبت شد ✅")
        return redirect("creator_apply")

    blockers = profile.publish_blockers()
    if profile.can_publish and profile.creator_enabled:
        return redirect("creator_studio")

    return render(
        request,
        "accounts/creator_apply.html",
        {
            "profile": profile,
            "blockers": blockers,
            "needs_phone": "phone" in blockers,
            "needs_handle": "handle" in blockers,
            "nav_active": "studio",
        },
    )


CREATOR_HANDLE_RESERVED = {
    # core
    "admin", "api", "static", "media", "staff", "healthz", "sitemap.xml",
    "robots.txt", "terms", "privacy", "about", "help", "support", "casset",
    # app routes
    "login", "logout", "register", "signup", "settings", "dashboard",
    "onboarding", "phone", "account", "auth", "google", "discover", "search",
    "trending", "upload", "uploads", "tracks", "track", "play", "plays",
    "playlist", "playlists", "billing", "subscriptions", "moderation",
    "explore", "library", "notifications", "albums", "album", "show",
    "shows", "vip", "payout", "creator", "embed", "my",
}


@login_required
def creator_handle_view(request):
    """Pick the public handle used for /<handle>/.

    Choosing one is the act that makes an account a publisher, so on
    success this also flips creator_enabled/creator_status — but only once
    the phone requirement is already satisfied.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.phone_verified:
        messages.info(request, "برای انتخاب یوزرنیم عمومی، اول شماره موبایلت را تایید کن.")
        return redirect("account_phone_start")

    if request.method == "POST":
        form = CreatorHandleForm(request.POST, instance=profile, reserved=CREATOR_HANDLE_RESERVED)
        if form.is_valid():
            form.save()
            profile.refresh_from_db()
            if profile.can_publish and profile.creator_status != UserProfile.CreatorStatus.REJECTED:
                profile.creator_enabled = True
                profile.creator_status = UserProfile.CreatorStatus.APPROVED
                profile.save(update_fields=["creator_enabled", "creator_status"])
            messages.success(request, "یوزرنیم عمومی شما ذخیره شد ✅ حالا می‌تونی منتشر کنی.")
            return redirect("creator_studio")
        messages.error(request, "خطا: لطفاً یک یوزرنیم معتبر انتخاب کن.")
    else:
        form = CreatorHandleForm(instance=profile, reserved=CREATOR_HANDLE_RESERVED)

    return render(
        request,
        "accounts/creator_handle.html",
        {"profile": profile, "form": form, "nav_active": "studio"},
    )


# ---------------------------------------------------------------------------
# Creator studio
# ---------------------------------------------------------------------------

@login_required
def creator_studio_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Content management — LIMIT at the DB, not in Python: list(qs)[:50] would
    # pull every track this creator has ever uploaded into memory before
    # slicing, which is a real cost for a prolific creator. qs[:50] is SQL
    # LIMIT 50, then list() just materializes that.
    my_tracks = list(
        Track.objects.filter(creator=request.user)
        .order_by("-created_at")
        .prefetch_related("genres")[:50]
    )

    # Analytics (last 30 days)
    from django.db.models import Count, Q, Sum
    from django.db.models.functions import TruncDate

    from plays.models import PlayEvent, PointLedger

    since = timezone.now() - timedelta(days=30)
    daily = (
        PlayEvent.objects.filter(track__creator=request.user, created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        # Count(..., filter=...), not Sum("point_awarded"): point_awarded is
        # a BooleanField, and SUM(boolean) is SQLite-only — it errors on
        # PostgreSQL ("function sum(boolean) does not exist"), which is what
        # production actually runs. Count with a filter is portable and
        # means the same thing here: "how many of today's plays qualified".
        .annotate(plays=Count("id"), points=Count("id", filter=Q(point_awarded=True)))
        .order_by("day")
    )
    daily = list(daily)

    # First-time vs. returning listeners in the window (Phase 4 — the same
    # split Spotify for Creators surfaces). Per-listener, not per-play:
    # a listener counts as "returning" if they played anything by this
    # creator before the window started, "first-time" otherwise.
    window_listener_ids = set(
        PlayEvent.objects.filter(
            track__creator=request.user, created_at__gte=since, user__isnull=False,
        ).values_list("user_id", flat=True).distinct()
    )
    prior_listener_ids = set(
        PlayEvent.objects.filter(
            track__creator=request.user, created_at__lt=since, user__isnull=False,
        ).values_list("user_id", flat=True).distinct()
    )
    returning_listeners = len(window_listener_ids & prior_listener_ids)
    first_time_listeners = len(window_listener_ids) - returning_listeners

    # Per-track breakdown for the same window — lets a creator see which
    # track is actually driving plays/points, not just a platform-wide total.
    plays_by_track = {
        row["track_id"]: row["plays"]
        for row in (
            PlayEvent.objects.filter(track__creator=request.user, created_at__gte=since)
            .values("track_id")
            .annotate(plays=Count("id"))
        )
    }
    points_by_track = {
        row["track_id_snapshot"]: row["points"]
        for row in (
            PointLedger.objects.filter(
                user=request.user, reason=PointLedger.Reason.PLAY_REWARD, created_at__gte=since,
            )
            .values("track_id_snapshot")
            .annotate(points=Sum("delta"))
        )
    }
    track_performance = [
        {
            "track": t,
            "plays": plays_by_track.get(t.id, 0),
            "points": points_by_track.get(t.id, 0),
        }
        for t in my_tracks
    ]

    # Sortable table: the creator decides what "top" means. Whitelisted
    # keys only — `sort` is user input and feeds a sort function.
    sort = request.GET.get("sort") or "plays"
    sorters = {
        "plays": lambda row: (-row["plays"], row["track"].title),
        "points": lambda row: (-row["points"], row["track"].title),
        "newest": lambda row: (-row["track"].id,),
        "title": lambda row: (row["track"].title,),
    }
    track_performance.sort(key=sorters.get(sort, sorters["plays"]))

    # Transparent earnings/points — every PointLedger row that touched this
    # creator's balance, not just the aggregate. This is the "why is my
    # balance what it is" view: award reasons, blocked-play audit entries,
    # and payout deductions all show up here from the same source of truth
    # (Constitution, CLAUDE.md §2 — UserProfile.points is a derived cache).
    from billing.models import PayoutRequest

    recent_ledger = list(
        PointLedger.objects.filter(user=request.user).order_by("-created_at")[:25]
    )
    recent_payouts = list(
        PayoutRequest.objects.filter(user=request.user).order_by("-created_at")[:10]
    )

    totals = {
        "plays": sum(d["plays"] for d in daily),
        "points": sum(d["points"] for d in daily),
        "tracks": len(my_tracks),
        "followers": profile.follower_count,
    }

    return render(
        request,
        "accounts/creator_studio.html",
        {
            "profile": profile,
            "tracks": my_tracks,
            "daily": daily,
            "chart_labels": [str(d["day"]) for d in daily],
            "chart_plays": [d["plays"] for d in daily],
            "chart_points": [d["points"] for d in daily],
            "totals": totals,
            "first_time_listeners": first_time_listeners,
            "returning_listeners": returning_listeners,
            "track_performance": track_performance,
            "sort": sort,
            "recent_ledger": recent_ledger,
            "recent_payouts": recent_payouts,
            "nav_active": "studio",
        },
    )


# ---------------------------------------------------------------------------
# Public profile
# ---------------------------------------------------------------------------

def profile_legacy_redirect(request, username):
    return redirect("public_profile", username=username)


def _public_profile_context(request, user_obj, profile, canonical_handle=False):
    """Shared context builder for both profile URL styles (/@username/ and
    /<handle>/). Pulled out once both views needed the same tab data
    (albums/shows/playlists) added on top of the already-duplicated
    tracks/stats/suggested-creators query — kept as one function instead of
    two near-identical copies."""
    from tracks.models import Album

    tracks = Track.objects.filter(
        creator=user_obj,
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    ).order_by("-created_at")

    music_tracks = [t for t in tracks if t.content_type != Track.ContentType.PODCAST][:50]
    podcast_tracks = [t for t in tracks if t.content_type == Track.ContentType.PODCAST][:50]

    albums = (
        Album.objects.filter(creator=user_obj, is_public=True)
        .exclude(content_type=Album.ContentType.PODCAST)
        .annotate(track_count=models.Count("tracks"))
        .order_by("-created_at")[:24]
    )
    shows = (
        Album.objects.filter(creator=user_obj, is_public=True, content_type=Album.ContentType.PODCAST)
        .annotate(track_count=models.Count("tracks"))
        .order_by("-created_at")[:24]
    )

    public_playlists = []
    if hasattr(user_obj, "playlists"):
        public_playlists = (
            user_obj.playlists.filter(is_private=False)
            .annotate(item_count=models.Count("items"))
            .order_by("-created_at")[:24]
        )

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

    return {
        "user_obj": user_obj,
        "profile": profile,
        "tracks": music_tracks,
        "podcast_tracks": podcast_tracks,
        "albums": albums,
        "shows": shows,
        "public_playlists": public_playlists,
        "stats": {
            "plays": total_plays,
            "likes": total_likes,
            "followers": followers_count,
            "following": following_count,
        },
        "suggested_creators": suggested,
        "canonical_handle": canonical_handle,
        "is_owner": request.user.is_authenticated and request.user.id == user_obj.id,
    }


def public_profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile, _ = UserProfile.objects.get_or_create(user=user_obj)

    # Canonical URL: if creator has a public handle, always redirect to /<handle>/
    # to avoid duplicate profile pages for the same person.
    if profile.public_handle:
        return redirect("public_profile_by_handle", handle=profile.public_handle)

    return render(
        request,
        "accounts/public_profile_pro.html",
        _public_profile_context(request, user_obj, profile),
    )


def public_profile_by_handle(request, handle):
    """Public profile reachable by /<handle>/ for creators."""
    profile = get_object_or_404(UserProfile, public_handle__iexact=handle)
    user_obj = profile.user

    return render(
        request,
        "accounts/public_profile_pro.html",
        _public_profile_context(request, user_obj, profile, canonical_handle=True),
    )


def api_user_connections(request, username):
    """JSON list of a user's followers or following, for the profile page's
    follower/following modal (previously the counts weren't clickable at
    all — this backs the new [data-connections] links in app.js)."""
    from django.http import JsonResponse

    user_obj = get_object_or_404(User, username=username)
    kind = request.GET.get("type")
    if kind not in ("followers", "following"):
        return JsonResponse({"ok": False, "error": "bad_type"}, status=400)

    if kind == "followers":
        rows = user_obj.followers.select_related("user__profile").order_by("-created_at")[:200]
        people = [r.user for r in rows]
    else:
        rows = user_obj.following.select_related("creator__profile").order_by("-created_at")[:200]
        people = [r.creator for r in rows]

    def _person(u):
        profile = getattr(u, "profile", None)
        return {
            "username": u.username,
            "name": profile.public_name() if profile else u.username,
            "avatar": profile.avatar.url if profile and profile.avatar else "",
            "verified": bool(profile and profile.is_verified),
            "url": profile.profile_url if profile else "",
        }

    return JsonResponse({"ok": True, "people": [_person(u) for u in people]})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@login_required
def settings_view(request):
    from notifications.models import NotificationPreference

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    prefs = NotificationPreference.for_user(request.user)

    form = ProfileSettingsForm(instance=profile)
    notif_form = NotificationPreferenceForm(instance=prefs)

    if request.method == "POST":
        section = request.POST.get("section") or "profile"

        if section == "notifications":
            notif_form = NotificationPreferenceForm(request.POST, instance=prefs)
            if notif_form.is_valid():
                notif_form.save()
                messages.success(request, "تنظیمات اعلان‌ها ذخیره شد ✅")
                return redirect(reverse("settings") + "#notifications")
            messages.error(request, "خطا در ذخیره تنظیمات اعلان‌ها.")
        else:
            form = ProfileSettingsForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, "تنظیمات پروفایل ذخیره شد ✅")
                return redirect("settings")
            messages.error(request, "خطا: لطفاً موارد را بررسی کن.")

    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "notif_form": notif_form,
            "profile": profile,
            "has_usable_password": request.user.has_usable_password(),
            "nav_active": "settings",
        },
    )


@login_required
@require_POST
def deactivate_account(request):
    """Self-service account deactivation.

    Deliberately NOT a delete: plays, ledger entries and payouts are
    financial and audit records that must stay re-derivable (Constitution).
    Deactivating hides the account and blocks login by the same mechanism
    staff suspension uses (User.is_active), which is already enforced on
    every entry point including OTP.
    """
    confirm = (request.POST.get("confirm") or "").strip()
    if confirm != request.user.username and confirm != (request.user.profile.public_handle or ""):
        messages.error(request, "برای تایید، نام کاربری خود را دقیقاً وارد کن.")
        return redirect(reverse("settings") + "#danger")

    profile = request.user.profile
    profile.suspended_at = timezone.now()
    profile.suspended_reason = "self_deactivated"
    profile.save(update_fields=["suspended_at", "suspended_reason"])

    request.user.is_active = False
    request.user.save(update_fields=["is_active"])

    # Hide the creator's public work along with the account — leaving
    # tracks playable under a deactivated profile would be the opposite of
    # what the user just asked for.
    Track.objects.filter(creator=request.user).update(visibility=Track.Visibility.PRIVATE)

    logout(request)
    messages.success(request, "حساب شما غیرفعال شد. برای بازگشت با پشتیبانی تماس بگیر.")
    return redirect("discover")


# ---------------------------------------------------------------------------
# Personal dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request):
    """User dashboard: points → revenue summary, plus 30-day trends.

    Points are read from PointLedger (source of truth), not from
    PlayEvent.point_awarded which is an implementation detail of
    the play-gating system.
    """
    from datetime import date

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    from core.models import PlatformSetting
    from plays.models import PlayEvent, PointLedger

    since_date = date.today() - timedelta(days=30)
    since = since_date.isoformat()
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

    # --- 30-day trend series, for the chart this page previously lacked ---
    # Zero-filled day by day: a gap in the data is a real zero, and a line
    # chart that silently skips days misreads as "no dip happened".
    plays_rows = {
        r["day"]: r["plays"]
        for r in (
            PlayEvent.objects.filter(track__creator=request.user, created_at__date__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(plays=Count("id"))
        )
    }
    points_rows = {
        r["day"]: int(r["points"] or 0)
        for r in (
            PointLedger.objects.filter(
                user=request.user,
                reason=PointLedger.Reason.PLAY_REWARD,
                created_at__date__gte=since,
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(points=Sum("delta"))
        )
    }
    labels, plays_series, points_series = [], [], []
    for offset in range(31):
        day = since_date + timedelta(days=offset)
        labels.append(day.isoformat())
        plays_series.append(plays_rows.get(day, 0))
        points_series.append(points_rows.get(day, 0))

    prev_since = since_date - timedelta(days=30)
    prev_plays = PlayEvent.objects.filter(
        track__creator=request.user,
        created_at__date__gte=prev_since,
        created_at__date__lt=since_date,
    ).count()
    cur_plays = sum(plays_series)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    return render(
        request,
        "accounts/dashboard.html",
        {
            "profile": profile,
            "points_by_type": points_by_type,
            "revenue_by_type": revenue_by_type,
            "total_points": total_points,
            "total_revenue": total_revenue,
            "since": since,
            "platform": platform,
            "chart_labels": labels,
            "chart_plays": plays_series,
            "chart_points": points_series,
            "plays_30d": cur_plays,
            "plays_delta_pct": _pct_delta(cur_plays, prev_plays),
            "followers": profile.follower_count,
            "track_count": Track.objects.filter(creator=request.user).count(),
            "nav_active": "dashboard",
        },
    )


def _pct_delta(current: int, previous: int):
    """Percentage change, or None when there is no baseline to compare to.

    Returning None rather than 0 or 100 matters: the template renders
    nothing at all instead of claiming a change that the data cannot
    support (the first 30 days of an account have no previous period).
    """
    if not previous:
        return None
    return round((current - previous) / previous * 100)
