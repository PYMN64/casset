from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import models

from core.models import PlatformSetting
from tracks.models import Track
from .forms import TrackUploadForm


def ensure_creator_profile(user):
    """Ensure the user has a profile.

    NOTE: We no longer auto-approve/enable creator mode here. Creator state
    is managed via the dedicated creator flow.
    """
    profile = getattr(user, "profile", None)
    if profile is None:
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


@login_required
def upload_track(request):
    ensure_creator_profile(request.user)

    setting = PlatformSetting.get_solo()
    form = TrackUploadForm(request.POST or None, request.FILES or None, user=request.user)

    if request.method == "POST":
        if form.is_valid():
            track = form.save(commit=False)
            track.creator = request.user
            track.status = Track.Status.DRAFT
            track.reject_reason = ""
            track.play_count = 0

            # Daily upload cap — anti-abuse, applies to every creator
            # (VIP only lifts the free-minutes cap below, not this one).
            uploads_today = Track.objects.filter(
                creator=request.user, created_at__date=timezone.localdate()
            ).count()
            if uploads_today >= setting.creator_daily_upload_limit:
                form.add_error(
                    None,
                    f"شما امروز به سقف {setting.creator_daily_upload_limit} آپلود رسیده‌اید. "
                    f"فردا دوباره تلاش کنید.",
                )
                return render(request, "uploads/upload.html", {"form": form, "setting": setting})

            # Free upload cap (minutes) for non-VIP creators
            profile = ensure_creator_profile(request.user)
            if not profile.has_vip():
                used = Track.objects.filter(creator=request.user).aggregate(
                    s=models.Sum("duration_seconds")
                )["s"] or 0
                new_dur = track.duration_seconds or 0
                cap_seconds = int(setting.free_upload_minutes) * 60
                if used + new_dur > cap_seconds:
                    remaining = max(0, cap_seconds - used)
                    form.add_error(
                        None,
                        f"سقف آپلود رایگان شما {int(setting.free_upload_minutes)} دقیقه است. "
                        f"باقی‌مانده: {remaining // 60} دقیقه. برای بیشتر VIP لازم است.",
                    )
                    # Don't save — fall through to re-render with error
                    return render(request, "uploads/upload.html", {"form": form, "setting": setting})

            track.save()
            form.save_m2m()
            messages.success(request, "محتوا به‌صورت پیش‌نویس ذخیره شد. برای بررسی و انتشار، آن را ارسال کنید.")
            return redirect("my_tracks")
        # invalid: fall-through to re-render with errors

    return render(request, "uploads/upload.html", {"form": form, "setting": setting})


@login_required
def my_tracks(request):
    qs = Track.objects.filter(creator=request.user).prefetch_related("genres").order_by("-created_at")
    return render(request, "uploads/my_tracks.html", {"tracks": qs})


@login_required
def edit_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, creator=request.user)
    setting = PlatformSetting.get_solo()
    form = TrackUploadForm(request.POST or None, request.FILES or None, instance=track, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.creator = request.user
        obj.save()
        form.save_m2m()
        messages.success(request, "تغییرات ذخیره شد.")
        return redirect("my_tracks")
    return render(request, "uploads/edit.html", {"form": form, "track": track, "setting": setting})


@login_required
def submit_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, creator=request.user)
    if request.method != "POST":
        raise Http404

    # Only allow submission from draft/rejected.
    if track.status not in [Track.Status.DRAFT, Track.Status.REJECTED, Track.Status.PENDING]:
        messages.error(request, "این محتوا در وضعیت فعلی قابل ارسال نیست.")
        return redirect("my_tracks")

    track.status = Track.Status.SUBMITTED
    track.submitted_at = timezone.now()
    track.reject_reason = ""
    track.save(update_fields=["status", "submitted_at", "reject_reason"])

    messages.success(request, "محتوا برای بررسی ارسال شد.")
    return redirect("my_tracks")
