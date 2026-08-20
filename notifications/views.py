"""notifications/views.py — Notification list and mark-as-read endpoints."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import Notification

logger = logging.getLogger("casset.notifications")

PAGE_SIZE = 30


@login_required
def notification_list(request):
    """Full notification inbox (HTML page)."""
    qs = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "actor__profile", "track", "comment")
        .order_by("-created_at")[:PAGE_SIZE]
    )
    unread_count = Notification.unread_count(request.user)
    return render(
        request,
        "notifications/list.html",
        {
            "notifications": qs,
            "unread_count": unread_count,
        },
    )


@login_required
def notification_api(request):
    """JSON feed for the bell-icon dropdown (last 10 unread)."""
    qs = (
        Notification.objects
        .filter(recipient=request.user, is_read=False)
        .select_related("actor", "actor__profile", "track")
        .order_by("-created_at")[:10]
    )
    data = []
    for n in qs:
        data.append({
            "id": n.pk,
            "verb": n.verb,
            "text": n.persian_text(),
            "track_slug": n.track.slug if n.track else None,
            "actor_handle": (
                n.actor.profile.public_handle or n.actor.username
                if n.actor and hasattr(n.actor, "profile")
                else None
            ),
            "created_at": n.created_at.isoformat(),
            "is_read": n.is_read,
        })
    return JsonResponse({
        "ok": True,
        "unread_count": Notification.unread_count(request.user),
        "notifications": data,
    })


@login_required
@require_POST
def mark_read(request):
    """Mark one or all notifications as read.

    POST body:
        notification_id (int, optional): mark one specific notification
        (no body): mark all as read
    """
    notif_id = request.POST.get("notification_id")
    if notif_id:
        try:
            notif = Notification.objects.get(
                pk=int(notif_id), recipient=request.user
            )
            notif.mark_read()
            updated = 1
        except (Notification.DoesNotExist, ValueError):
            return JsonResponse({"ok": False, "error": "not_found"}, status=404)
    else:
        updated = Notification.mark_all_read(request.user)

    unread = Notification.unread_count(request.user)

    # A plain form POST (no JavaScript) must land back on the page, not on
    # a screenful of raw JSON — which is exactly what this endpoint used to
    # return to the notification list's own non-AJAX form.
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        from django.shortcuts import redirect

        return redirect("notification_list")

    return JsonResponse({
        "ok": True,
        "updated": updated,
        "unread_count": unread,
    })
