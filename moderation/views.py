from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.utils import timezone

from tracks.models import Track
from plays.models import FraudFlag

from .models import Report, AuditLog

User = get_user_model()


def _report_rate_limited(user_id: int, target_key: str) -> bool:
    """1 report per day per user per target."""
    day = date.today().isoformat()
    key = f"rl:report:{user_id}:{target_key}:{day}"
    if cache.get(key):
        return True
    cache.set(key, 1, timeout=24*3600)
    return False


def _wants_json(request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in accept


@require_POST
@login_required
def report_profile(request, username: str):
    target = get_object_or_404(User, username=username)
    if target.id == request.user.id:
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': 'cannot_report_self'}, status=400)
        messages.error(request, "You cannot report yourself.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    target_key = f"profile:{target.id}"
    if _report_rate_limited(request.user.id, target_key):
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': 'rate_limited'}, status=429)
        messages.error(request, "You have already reported this profile today.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    reason = request.POST.get('reason') or Report.Reason.IMPERSONATION
    details = request.POST.get('details','')

    Report.objects.create(
        reporter=request.user,
        target_type=Report.TargetType.PROFILE,
        target_user=target,
        reported_username=username,
        reason=reason,
        details=details,
    )

    if _wants_json(request):
        return JsonResponse({'ok': True})
    messages.success(request, "Report submitted.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
@login_required
def report_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id)
    target_key = f"track:{track.id}"
    if _report_rate_limited(request.user.id, target_key):
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': 'rate_limited'}, status=429)
        messages.error(request, "You have already reported this track today.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    reason = request.POST.get('reason') or Report.Reason.OTHER
    details = request.POST.get('details','')
    Report.objects.create(
        reporter=request.user,
        target_type=Report.TargetType.TRACK,
        track=track,
        reason=reason,
        details=details,
    )
    if _wants_json(request):
        return JsonResponse({'ok': True})
    messages.success(request, "Report submitted.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def _staff_required(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404


def track_queue(request):
    _staff_required(request)
    qs = Track.objects.filter(status__in=[Track.Status.SUBMITTED, Track.Status.PENDING]).select_related('creator').order_by('-submitted_at','-created_at')
    return render(request, 'moderation/track_queue.html', {'tracks': qs[:200]})


@require_POST
def approve_track(request, track_id: int):
    _staff_required(request)
    track = get_object_or_404(Track, id=track_id)
    track.status = Track.Status.APPROVED
    track.reject_reason = ""
    track.published_at = timezone.now()
    if track.visibility == Track.Visibility.PRIVATE:
        track.visibility = Track.Visibility.PUBLIC
    track.save(update_fields=['status','reject_reason','published_at','visibility'])
    AuditLog.objects.create(actor=request.user, target_type=AuditLog.TargetType.TRACK, track=track, action='approve_track')
    return redirect('moderation_track_queue')


@require_POST
def reject_track(request, track_id: int):
    _staff_required(request)
    track = get_object_or_404(Track, id=track_id)
    reason = (request.POST.get('reason') or '').strip()[:240]
    track.status = Track.Status.REJECTED
    track.reject_reason = reason or "Rejected"
    track.save(update_fields=['status','reject_reason'])
    AuditLog.objects.create(actor=request.user, target_type=AuditLog.TargetType.TRACK, track=track, action='reject_track', metadata={'reason': track.reject_reason})
    return redirect('moderation_track_queue')


def report_queue(request):
    _staff_required(request)
    qs = Report.objects.all().select_related('reporter','track','target_user').order_by('-created_at')
    return render(request, 'moderation/report_queue.html', {'reports': qs[:200]})


def fraud_queue(request):
    _staff_required(request)
    qs = FraudFlag.objects.select_related('user', 'track').order_by('-created_at')
    return render(request, 'moderation/fraud_queue.html', {'flags': qs[:200]})
