import json
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from billing.models import Invoice, PayoutRequest
from moderation import services as moderation_services
from moderation.models import Report
from plays.models import PlayEvent, PointLedger
from tracks.models import Track

User = get_user_model()

_PAGE_SIZE = 30


def _paginate(request, qs):
    paginator = Paginator(qs, _PAGE_SIZE)
    page_number = request.GET.get("page") or 1
    return paginator.get_page(page_number)


def _daily_series(day_values: dict, days: int = 30) -> tuple[list[str], list]:
    """Fill in a contiguous last-`days` date range so the chart's x-axis
    never has gaps for days with zero activity — `day_values` only has
    entries for days that actually happened something.

    `day_values` keys may be `date` objects or ISO strings (PlayEvent.day_key
    is already a string; the Invoice/PointLedger/User queries below produce
    real `date` objects via TruncDate) — normalised to string here so both
    callers can share this helper.
    """
    normalised = {
        (k.isoformat() if hasattr(k, "isoformat") else str(k)): v
        for k, v in day_values.items()
    }
    today = timezone.localdate()
    labels, values = [], []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        labels.append(day)
        values.append(normalised.get(day, 0))
    return labels, values


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
    page = _paginate(request, qs)
    extra_qs = f"q={q}" if q else ""
    return render(request, "staff/users_console.html", {"profiles": page, "page_obj": page, "q": q, "extra_qs": extra_qs})


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
    page = _paginate(request, qs)
    extra_qs = "&".join(p for p in [f"q={q}" if q else "", f"status={status}" if status else ""] if p)
    return render(
        request,
        "staff/creators_console.html",
        {"profiles": page, "page_obj": page, "q": q, "status": status, "extra_qs": extra_qs},
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
    top_tracks = list(
        Track.objects.filter(creator_id=user_id).order_by("-play_count")[:8]
    )
    chart = {
        "labels": [t.title[:20] for t in top_tracks],
        "values": [t.play_count for t in top_tracks],
    }
    return render(
        request,
        "staff/creator_detail.html",
        {"profile": profile, "tracks": tracks, "totals": totals, "chart_data": chart},
    )


@staff_member_required
@require_POST
def toggle_verified(request, user_id: int):
    user = get_object_or_404(User, id=user_id)
    moderation_services.set_verified(
        user=user, actor=request.user, verified=not user.profile.is_verified,
    )
    return redirect("staff:creator_detail", user_id=user_id)


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

    cutoff = (timezone.localdate() - timedelta(days=29)).isoformat()

    plays_by_day = dict(
        PlayEvent.objects.filter(point_awarded=True, day_key__gte=cutoff)
        .values("day_key").annotate(c=Count("id")).order_by("day_key")
        .values_list("day_key", "c")
    )
    plays_labels, plays_values = _daily_series(plays_by_day)

    revenue_by_day = dict(
        Invoice.objects.filter(status=Invoice.Status.PAID, paid_at__date__gte=cutoff)
        .annotate(day=TruncDate("paid_at")).values("day")
        .annotate(total=Sum("amount")).order_by("day")
        .values_list("day", "total")
    )
    revenue_labels, revenue_values = _daily_series(revenue_by_day)
    revenue_values = [float(v) for v in revenue_values]

    points_rows = (
        PointLedger.objects.filter(created_at__date__gte=cutoff)
        .annotate(day=TruncDate("created_at")).values("day")
        .annotate(
            issued=Sum("delta", filter=Q(delta__gt=0)),
            redeemed=Sum("delta", filter=Q(delta__lt=0)),
        ).order_by("day")
    )
    points_issued_by_day = {r["day"]: r["issued"] or 0 for r in points_rows}
    points_redeemed_by_day = {r["day"]: -(r["redeemed"] or 0) for r in points_rows}
    points_labels, points_issued_series = _daily_series(points_issued_by_day)
    _, points_redeemed_series = _daily_series(points_redeemed_by_day)

    signups_by_day = dict(
        User.objects.filter(date_joined__date__gte=cutoff)
        .annotate(day=TruncDate("date_joined")).values("day")
        .annotate(c=Count("id")).order_by("day")
        .values_list("day", "c")
    )
    signup_labels, signup_values = _daily_series(signups_by_day)

    charts = {
        "plays": {"labels": plays_labels, "values": plays_values},
        "revenue": {"labels": revenue_labels, "values": revenue_values},
        "points": {"labels": points_labels, "issued": points_issued_series, "redeemed": points_redeemed_series},
        "signups": {"labels": signup_labels, "values": signup_values},
    }

    return render(
        request,
        "staff/platform_dashboard.html",
        {
            "revenue_total": revenue_total,
            "charts_data": charts,
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
