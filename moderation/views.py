from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from interactions.models import Comment
from tracks.models import Track

from . import services
from .models import Report

User = get_user_model()

_PAGE_SIZE = 30


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
    from core.models import PlatformSetting

    qs = Track.objects.filter(status__in=[Track.Status.SUBMITTED, Track.Status.PENDING]).select_related('creator').order_by('-submitted_at','-created_at')
    page = Paginator(qs, _PAGE_SIZE).get_page(request.GET.get('page') or 1)
    return render(request, 'moderation/track_queue.html', {
        'tracks': page,
        'page_obj': page,
        'platform': PlatformSetting.get_solo(),
    })


@require_POST
def approve_track(request, track_id: int):
    _staff_required(request)
    track = get_object_or_404(Track, id=track_id)
    # services.approve_track() is idempotent (no-op if already approved) —
    # see its docstring for why that matters on re-click/revisit.
    services.approve_track(track=track, actor=request.user)
    return redirect('moderation_track_queue')


@require_POST
def reject_track(request, track_id: int):
    _staff_required(request)
    track = get_object_or_404(Track, id=track_id)
    reason = (request.POST.get('reason') or '').strip()[:240]
    services.reject_track(track=track, actor=request.user, reason=reason)
    return redirect('moderation_track_queue')


def report_queue(request):
    _staff_required(request)
    qs = (
        Report.objects.all()
        .select_related('reporter', 'track', 'target_user', 'comment', 'comment__author')
        .order_by('-created_at')
    )
    status = (request.GET.get('status') or '').strip()
    if status:
        qs = qs.filter(status=status)
    page = Paginator(qs, _PAGE_SIZE).get_page(request.GET.get('page') or 1)
    extra_qs = f"status={status}" if status else ""
    return render(request, 'moderation/report_queue.html', {
        'reports': page,
        'page_obj': page,
        'report_statuses': Report.Status.choices,
        'status': status,
        'extra_qs': extra_qs,
    })


@require_POST
def update_report(request, report_id: int):
    _staff_required(request)
    report = get_object_or_404(Report, id=report_id)
    status = request.POST.get('status') or ''
    note = request.POST.get('note') or ''
    if not services.update_report_status(report=report, actor=request.user, status=status, note=note):
        return JsonResponse({'ok': False, 'error': 'invalid_status'}, status=400)
    return redirect('moderation_report_queue')


@require_POST
def restore_comment_view(request, comment_id: int):
    _staff_required(request)
    comment = get_object_or_404(Comment, id=comment_id)
    services.restore_comment(comment=comment, actor=request.user)
    return redirect('moderation_report_queue')


@require_POST
def suspend_profile(request, username: str):
    _staff_required(request)
    target = get_object_or_404(User, username=username)
    reason = (request.POST.get('reason') or '').strip()
    services.suspend_user(user=target, actor=request.user, reason=reason)
    return redirect('moderation_report_queue')


@require_POST
def unsuspend_profile(request, username: str):
    _staff_required(request)
    target = get_object_or_404(User, username=username)
    services.unsuspend_user(user=target, actor=request.user)
    return redirect('moderation_report_queue')
