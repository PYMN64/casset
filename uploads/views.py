from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import PlatformSetting
from tracks.models import Track
from .forms import TrackUploadForm


def ensure_creator_profile(user):
    profile = getattr(user, "profile", None)
    if profile is None:
        from accounts.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


@login_required
def upload_track(request):
    profile = ensure_creator_profile(request.user)

    setting = PlatformSetting.get_solo()
    form = TrackUploadForm(request.POST or None, request.FILES or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        track = form.save(commit=False)
        track.creator = request.user
        track.status = Track.Status.DRAFT
        track.reject_reason = ""

        today = timezone.now().date()
        daily_limit = int(setting.creator_daily_upload_limit or 0)
        daily_count = Track.objects.filter(creator=request.user, created_at__date=today).count()
        if daily_limit > 0 and daily_count >= daily_limit:
            form.add_error(
                None,
                "Daily upload limit reached. Try again tomorrow.",
            )
        else:
            if not request.user.profile.has_vip():
                used = (
                    Track.objects.filter(creator=request.user).aggregate(s=models.Sum("duration_seconds"))["s"]
                    or 0
                )
                new_dur = track.duration_seconds or 0
                cap_seconds = int(setting.free_upload_minutes) * 60
                if used + new_dur > cap_seconds:
                    remaining = max(0, cap_seconds - used)
                    form.add_error(
                        None,
                        f"Free upload cap is {int(setting.free_upload_minutes)} minutes. Remaining: {remaining // 60} minutes.",
                    )
                else:
                    track.play_count = 0
                    track.save()
                    form.save_m2m()
                    messages.success(
                        request,
                        "Saved as draft. Submit for review when ready.",
                    )
                    return redirect("my_tracks")
            else:
                track.play_count = 0
                track.save()
                form.save_m2m()
                messages.success(
                    request,
                    "Saved as draft. Submit for review when ready.",
                )
                return redirect("my_tracks")

    return render(
        request,
        "uploads/upload.html",
        {
            "form": form,
            "setting": setting,
            "creator_can_submit": profile.creator_status == profile.CreatorStatus.APPROVED,
            "disabled_content_types": getattr(form, "disabled_content_types", set()),
        },
    )


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
        messages.success(request, "Changes saved.")
        return redirect("my_tracks")
    return render(
        request,
        "uploads/edit.html",
        {
            "form": form,
            "track": track,
            "setting": setting,
            "disabled_content_types": getattr(form, "disabled_content_types", set()),
        },
    )


@login_required
def submit_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, creator=request.user)
    if request.method != "POST":
        raise Http404

    profile = ensure_creator_profile(request.user)
    if profile.creator_status != profile.CreatorStatus.APPROVED:
        messages.error(request, "Creator approval required before submission.")
        return redirect("creator_apply")

    if track.status not in [Track.Status.DRAFT, Track.Status.REJECTED, Track.Status.PENDING]:
        messages.error(request, "This track is not eligible for submission.")
        return redirect("my_tracks")

    track.status = Track.Status.SUBMITTED
    track.submitted_at = timezone.now()
    track.reject_reason = ""
    track.save(update_fields=["status", "submitted_at", "reject_reason"])

    messages.success(request, "Submitted for review.")
    return redirect("my_tracks")
