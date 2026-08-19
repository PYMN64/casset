from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from interactions.models import Comment
from tracks.models import Track

from . import services
from .models import AuditLog, Report

User = get_user_model()


def _already_reported_today(user_id: int, target_key: str, *, queryset) -> bool:
    """Return True if this user already reported this target today.

    Design
    ------
    The database is the source of truth: cache alone is not safe here,
    because a cache flush or eviction would let the same user file the
    same report again. Cache is only a fast path that avoids a DB hit
    on the common (already-reported) case.

    The day boundary uses the project's local timezone, so "today"
    matches what the user sees rather than the server's UTC clock.
    """
    today = timezone.localdate()
    key = f"report:{user_id}:{target_key}:{today.isoformat()}"

    if cache.get(key):
        return True

    exists = queryset.filter(
        reporter_id=user_id, created_at__date=today
    ).exists()

    if exists:
        cache.set(key, 1, timeout=24 * 3600)
    return exists


def _mark_reported(user_id: int, target_key: str) -> None:
    """Warm the cache after a successful report."""
    today = timezone.localdate()
    cache.set(
        f"report:{user_id}:{target_key}:{today.isoformat()}", 1, timeout=24 * 3600
    )


@require_POST
@login_required
def report_profile(request, username: str):
    # allow reporting even if username exists; we also store reported_username for claims
    target = get_object_or_404(User, username=username)
    if target.id == request.user.id:
        return JsonResponse({'ok': False, 'error': 'cannot_report_self'}, status=400)

    target_key = f"profile:{target.id}"
    if _already_reported_today(
        request.user.id, target_key,
        queryset=Report.objects.filter(
            target_type=Report.TargetType.PROFILE, target_user=target
        ),
    ):
        return JsonResponse(
            {'ok': False, 'error': 'already_reported_today'}, status=429
        )

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
    _mark_reported(request.user.id, target_key)
    return JsonResponse({'ok': True})


@require_POST
@login_required
def report_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id)
    target_key = f"track:{track.id}"

    if _already_reported_today(
        request.user.id, target_key,
        queryset=Report.objects.filter(
            target_type=Report.TargetType.TRACK, track=track
        ),
    ):
        return JsonResponse(
            {'ok': False, 'error': 'already_reported_today'}, status=429
        )

    reason = request.POST.get('reason') or Report.Reason.OTHER
    details = request.POST.get('details','')
    Report.objects.create(
        reporter=request.user,
        target_type=Report.TargetType.TRACK,
        track=track,
        reason=reason,
        details=details,
    )
    _mark_reported(request.user.id, target_key)
    return JsonResponse({'ok': True})


@require_POST
@login_required
def report_comment(request, comment_id: int):
    comment = get_object_or_404(Comment, id=comment_id)
    target_key = f"comment:{comment.id}"

    if _already_reported_today(
        request.user.id, target_key,
        queryset=Report.objects.filter(
            target_type=Report.TargetType.COMMENT, comment=comment
        ),
    ):
        return JsonResponse(
            {'ok': False, 'error': 'already_reported_today'}, status=429
        )

    reason = request.POST.get('reason') or Report.Reason.ABUSE
    details = request.POST.get('details', '')
    Report.objects.create(
        reporter=request.user,
        target_type=Report.TargetType.COMMENT,
        comment=comment,
        reason=reason,
        details=details,
    )
    _mark_reported(request.user.id, target_key)
    hidden = services.check_and_auto_hide_comment(comment=comment)
    return JsonResponse({'ok': True, 'auto_hidden': hidden})


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
    if track.status == Track.Status.APPROVED:
        # Idempotent no-op: without this, re-clicking (or revisiting the
        # URL) resends the "track approved" notification every time — the
        # signal in notifications/signals.py has no dedup of its own — and
        # bumps published_at to a new timestamp on every re-click.
        return redirect('moderation_track_queue')
    track.status = Track.Status.APPROVED
    track.reject_reason = ""
    track.published_at = timezone.now()
    # default to public when approved if still private
    if track.visibility == Track.Visibility.PRIVATE:
        track.visibility = Track.Visibility.PUBLIC
    track.save(update_fields=['status','reject_reason','published_at','visibility'])
    AuditLog.objects.create(actor=request.user, target_type=AuditLog.TargetType.TRACK, track=track, action='approve_track')
    return redirect('moderation_track_queue')


@require_POST
def reject_track(request, track_id: int):
    _staff_required(request)
    track = get_object_or_404(Track, id=track_id)
    if track.status == Track.Status.REJECTED:
        # Same idempotency reasoning as approve_track — avoid a duplicate
        # "track rejected" notification on re-click/resubmission.
        return redirect('moderation_track_queue')
    reason = (request.POST.get('reason') or '').strip()[:240]
    track.status = Track.Status.REJECTED
    track.reject_reason = reason or "رد شد"
    track.save(update_fields=['status','reject_reason'])
    AuditLog.objects.create(actor=request.user, target_type=AuditLog.TargetType.TRACK, track=track, action='reject_track', metadata={'reason': track.reject_reason})
    return redirect('moderation_track_queue')


def report_queue(request):
    _staff_required(request)
    qs = Report.objects.all().select_related('reporter','track','target_user').order_by('-created_at')
    return render(request, 'moderation/report_queue.html', {'reports': qs[:200]})
