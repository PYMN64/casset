from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render

from accounts.models import UserProfile
from billing.models import Invoice, PayoutRequest
from moderation.models import Report
from plays.models import PlayEvent, PointLedger
from tracks.models import Track


@staff_member_required
def users_console(request):
    qs = (
        UserProfile.objects.select_related("user")
        .annotate(
            tracks_count=Count("user__tracks", distinct=True),
            plays_count=Count("user__tracks__play_events", distinct=False),
            # Count(..., filter=...), not Sum(BooleanField): SUM(boolean) is
            # SQLite-only (silently tolerated) and errors on PostgreSQL with
            # "function sum(boolean) does not exist" — same class of bug as
            # accounts/views.py::creator_studio_view (CLAUDE.md item #13),
            # caught here by the same live-Postgres verification pass. This
            # view was previously unreachable (core.staff_urls was never
            # mounted in config/urls.py until this session), so the bug had
            # never actually been hit before.
            points_earned=Count(
                "user__tracks__play_events",
                filter=Q(user__tracks__play_events__point_awarded=True),
            ),
        )
        .order_by("-created_at")
    )
    # simple search
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(user__username__icontains=q) | Q(display_name__icontains=q) | Q(public_handle__icontains=q) | Q(user__email__icontains=q))
    return render(request, "staff/users_console.html", {"profiles": qs, "q": q})


@staff_member_required
def creators_console(request):
    qs = (
        UserProfile.objects.select_related("user")
        .filter(creator_status__in=["pending", "approved"])
        .annotate(
            tracks_count=Count("user__tracks", distinct=True),
            valid_plays=Count(
                "user__tracks__play_events",
                filter=Q(user__tracks__play_events__point_awarded=True),
            ),
        )
        .order_by("-updated_at")
    )
    status = (request.GET.get("status") or "").strip()
    if status in ("pending", "approved"):
        qs = qs.filter(creator_status=status)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(user__username__icontains=q) | Q(display_name__icontains=q) | Q(public_handle__icontains=q) | Q(user__email__icontains=q))
    return render(
        request,
        "staff/creators_console.html",
        {"profiles": qs, "q": q, "status": status},
    )


@staff_member_required
def creator_detail(request, user_id: int):
    profile = get_object_or_404(UserProfile.objects.select_related("user"), user_id=user_id)
    tracks = Track.objects.filter(creator_id=user_id).order_by("-created_at")[:50]
    totals = (
        PlayEvent.objects.filter(track__creator_id=user_id)
        .aggregate(
            plays=Count("id"),
            valid_plays=Count("id", filter=Q(point_awarded=True)),
        )
    )
    return render(
        request,
        "staff/creator_detail.html",
        {"profile": profile, "tracks": tracks, "totals": totals},
    )


@staff_member_required
def platform_dashboard(request):
    """Platform-wide overview: revenue, points economy, and the queues that
    need staff attention right now — a real admin home instead of three
    disconnected list pages (users/creators consoles, moderation queues)
    each requiring a separate visit to check on."""
    revenue_total = (
        Invoice.objects.filter(status=Invoice.Status.PAID).aggregate(total=Sum("amount"))["total"] or 0
    )

    points_summary = PointLedger.objects.aggregate(
        issued=Sum("delta", filter=Q(delta__gt=0)),
        redeemed=Sum("delta", filter=Q(delta__lt=0)),
    )
    points_issued = points_summary["issued"] or 0
    points_redeemed = -(points_summary["redeemed"] or 0)

    pending_payouts = PayoutRequest.objects.filter(status=PayoutRequest.Status.PENDING)
    pending_payout_amount = pending_payouts.aggregate(total=Sum("amount"))["total"] or 0

    return render(
        request,
        "staff/platform_dashboard.html",
        {
            "revenue_total": revenue_total,
            "points_issued": points_issued,
            "points_redeemed": points_redeemed,
            "points_outstanding": points_issued - points_redeemed,
            "active_creators": UserProfile.objects.filter(
                creator_status=UserProfile.CreatorStatus.APPROVED
            ).count(),
            "pending_creators": UserProfile.objects.filter(
                creator_status=UserProfile.CreatorStatus.PENDING
            ).count(),
            "pending_tracks": Track.objects.filter(
                status__in=[Track.Status.SUBMITTED, Track.Status.PENDING]
            ).count(),
            "pending_reports": Report.objects.filter(status=Report.Status.PENDING).count(),
            "pending_payout_count": pending_payouts.count(),
            "pending_payout_amount": pending_payout_amount,
            "suspended_users": UserProfile.objects.filter(suspended_at__isnull=False).count(),
        },
    )
