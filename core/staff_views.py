from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, render

from accounts.models import UserProfile
from tracks.models import Track
from plays.models import PlayEvent


@staff_member_required
def users_console(request):
    qs = (
        UserProfile.objects.select_related("user")
        .annotate(
            tracks_count=Count("user__tracks", distinct=True),
            plays_count=Count("user__tracks__play_events", distinct=False),
            points_earned=Sum(
                "user__tracks__play_events__point_awarded",
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
