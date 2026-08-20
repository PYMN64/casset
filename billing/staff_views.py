"""billing/staff_views.py — staff payout approval queue.

Follows the same pattern as moderation/views.py's report/track queues: one
list view, one POST-per-action form, business logic in services.py (billing/
services.py::approve_payout/reject_payout), views stay thin.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .models import PayoutRequest


@staff_member_required
def payout_queue(request):
    payouts = (
        PayoutRequest.objects.filter(status=PayoutRequest.Status.PENDING)
        .select_related("user", "user__profile")
        .order_by("created_at")
    )
    page = Paginator(payouts, 30).get_page(request.GET.get("page") or 1)
    # Previously there was no visibility into past decisions at all — every
    # approve/reject vanished from this page the moment it happened.
    history = (
        PayoutRequest.objects.exclude(status=PayoutRequest.Status.PENDING)
        .select_related("user", "user__profile")
        .order_by("-created_at")[:20]
    )
    return render(request, "billing/staff_payout_queue.html", {
        "payouts": page, "page_obj": page, "history": history,
    })


@staff_member_required
@require_POST
def approve_payout(request, payout_id: int):
    payout = get_object_or_404(PayoutRequest, id=payout_id)
    services.approve_payout(payout=payout, actor=request.user)
    return redirect("staff_payout_queue")


@staff_member_required
@require_POST
def reject_payout(request, payout_id: int):
    payout = get_object_or_404(PayoutRequest, id=payout_id)
    reason = (request.POST.get("reason") or "").strip()[:500]
    services.reject_payout(payout=payout, actor=request.user, reason=reason)
    return redirect("staff_payout_queue")
