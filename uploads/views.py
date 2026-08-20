from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
            if track.audio:
                from tracks.tasks import generate_waveform_task
                generate_waveform_task.delay(track_id=track.id)
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
        audio_changed = "audio" in form.changed_data
        obj = form.save(commit=False)
        obj.creator = request.user
        obj.save()
        form.save_m2m()
        if audio_changed and obj.audio:
            from tracks.tasks import generate_waveform_task
            generate_waveform_task.delay(track_id=obj.id)
        messages.success(request, "تغییرات ذخیره شد.")
        return redirect("my_tracks")
    return render(request, "uploads/edit.html", {"form": form, "track": track, "setting": setting})


@login_required
@require_POST
def toggle_track_visibility(request, track_id: int):
    """Self-service unpublish/republish for an approved track's creator.

    Not a hard delete — flips `visibility` between PUBLIC and PRIVATE, the
    same field moderation/admin already use to hide content. This keeps
    play history, points and audit records intact (Constitution: derived
    data must stay reconstructable) while immediately removing the track
    from public listings and blocking new plays (see plays/views.py
    `_is_playable`). A creator can always republish it again from here.
    """
    track = get_object_or_404(Track, id=track_id, creator=request.user)
    if track.status != Track.Status.APPROVED:
        messages.error(request, "فقط محتوای منتشرشده قابل مخفی/نمایش‌کردن است.")
        return redirect("my_tracks")

    if track.visibility == Track.Visibility.PRIVATE:
        track.visibility = Track.Visibility.PUBLIC
        messages.success(request, f"«{track.title}» دوباره منتشر شد ✅")
    else:
        track.visibility = Track.Visibility.PRIVATE
        messages.success(request, f"«{track.title}» از دید عموم مخفی شد.")
    track.save(update_fields=["visibility"])
    return redirect("my_tracks")


@login_required
def submit_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, creator=request.user)
    if request.method != "POST":
        raise Http404

    # Publisher gate.
    #
    # Uploading a draft is open to any signed-in account — a draft is
    # private and harmless. Submitting for review is the moment content
    # becomes public-bound, so this is where the product rule applies:
    # a publisher must have a verified phone number and a public handle
    # (accounts.models.UserProfile.can_publish). Gating at upload time
    # instead would block people from preparing work before they finish
    # setting up, for no safety benefit.
    profile = ensure_creator_profile(request.user)
    if not profile.can_publish:
        messages.error(
            request,
            "برای انتشار اثر، ابتدا شماره موبایلت را تایید کن و یوزرنیم عمومی انتخاب کن.",
        )
        return redirect("creator_apply")

    # Only allow submission from draft/rejected.
    if track.status not in [Track.Status.DRAFT, Track.Status.REJECTED, Track.Status.PENDING]:
        messages.error(request, "این محتوا در وضعیت فعلی قابل ارسال نیست.")
        return redirect("my_tracks")

    track.status = Track.Status.SUBMITTED
    track.submitted_at = timezone.now()
    track.reject_reason = ""
    track.save(update_fields=["status", "submitted_at", "reject_reason"])

    setting = PlatformSetting.get_solo()
    if setting.auto_approve_tracks:
        from moderation.services import approve_track

        approve_track(track=track, actor=None)
        messages.success(request, "محتوا فوراً منتشر شد ✅ (تایید خودکار فعال است).")
    else:
        messages.success(request, "محتوا برای بررسی ارسال شد.")
    return redirect("my_tracks")
