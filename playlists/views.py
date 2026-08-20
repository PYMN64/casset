from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from interactions.models import TrackLike
from tracks.models import Track

from .models import Playlist, PlaylistItem


@login_required
def library_view(request):
    playlists = list(
        Playlist.objects.filter(owner=request.user)
        .annotate(item_count=Count("items"))
        .order_by("-created_at")
    )

    # Cover artwork per playlist: the artwork of its first item. Fetched in
    # one query for the whole page rather than one per playlist — a library
    # with 30 playlists would otherwise fire 30 extra queries just to draw
    # thumbnails.
    if playlists:
        first_items = (
            PlaylistItem.objects.filter(playlist__in=playlists)
            .select_related("track")
            .order_by("playlist_id", "order", "-created_at")
        )
        cover_by_playlist = {}
        for item in first_items:
            cover_by_playlist.setdefault(item.playlist_id, item.track)
        for pl in playlists:
            pl.cover_track = cover_by_playlist.get(pl.id)

    liked_track_ids = (
        TrackLike.objects.filter(user=request.user)
        .order_by("-created_at")
        .values_list("track_id", flat=True)[:200]
    )
    liked_tracks = (
        Track.objects.filter(id__in=list(liked_track_ids), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        .select_related("creator", "creator__profile")
        .prefetch_related("genres")
    )

    return render(request, "library/library.html", {
        "playlists": playlists,
        "liked_tracks": liked_tracks,
        "nav_active": "library",
    })


def playlist_detail(request, playlist_id: int):
    """A playlist is visible to its owner always, and to everyone else only
    when `is_private=False` — this is also what the public-profile "Playlists"
    tab links to (accounts/views.py::_public_profile_context), so a private
    playlist reached that way must 404 exactly like a private track does."""
    pl = get_object_or_404(Playlist, id=playlist_id)
    is_owner = request.user.is_authenticated and pl.owner_id == request.user.id
    if pl.is_private and not is_owner:
        raise Http404
    items = (
        PlaylistItem.objects.filter(playlist=pl)
        .select_related("track", "track__creator", "track__creator__profile")
        .prefetch_related("track__genres")
        .order_by("order", "-created_at")
    )
    items = list(items)
    total_seconds = sum((it.track.duration_seconds or 0) for it in items)
    return render(request, "playlists/playlist_detail.html", {
        "pl": pl,
        "items": items,
        "is_owner": is_owner,
        "total_seconds": total_seconds,
        "total_minutes": total_seconds // 60,
        "nav_active": "library",
    })


@require_POST
@login_required
def api_playlist_create(request):
    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()

    if not name or len(name) > 80:
        return JsonResponse({"ok": False, "reason": "invalid_name"}, status=400)

    pl = Playlist.objects.create(
        owner=request.user,
        name=name,
        description=description[:200],
        is_private=True,
    )
    return JsonResponse({"ok": True, "playlist_id": pl.id, "name": pl.name})


@require_POST
@login_required
def api_playlist_delete(request):
    pid = request.POST.get("playlist_id")
    if not pid or not str(pid).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_playlist_id"}, status=400)

    pl = Playlist.objects.filter(id=int(pid), owner=request.user).first()
    if not pl:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    pl.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required
def api_playlist_toggle_track(request):
    pid = request.POST.get("playlist_id")
    tid = request.POST.get("track_id")

    if not pid or not str(pid).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_playlist_id"}, status=400)
    if not tid or not str(tid).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_track_id"}, status=400)

    pl = Playlist.objects.filter(id=int(pid), owner=request.user).first()
    if not pl:
        return JsonResponse({"ok": False, "reason": "playlist_not_found"}, status=404)

    track = Track.objects.filter(id=int(tid), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC).first()
    if not track:
        return JsonResponse({"ok": False, "reason": "track_not_found"}, status=404)

    added = False
    try:
        with transaction.atomic():
            next_order = (
                PlaylistItem.objects.filter(playlist=pl).aggregate(m=Max("order"))["m"] or 0
            ) + 1
            PlaylistItem.objects.create(playlist=pl, track=track, order=next_order)
            added = True
    except IntegrityError:
        PlaylistItem.objects.filter(playlist=pl, track=track).delete()
        added = False

    count = PlaylistItem.objects.filter(playlist=pl).count()
    return JsonResponse({"ok": True, "added": added, "count": count})


@require_POST
@login_required
def api_playlist_rename(request):
    pid = request.POST.get("playlist_id")
    name = (request.POST.get("name") or "").strip()
    if not pid or not str(pid).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_playlist_id"}, status=400)
    if not name or len(name) > 80:
        return JsonResponse({"ok": False, "reason": "invalid_name"}, status=400)

    pl = Playlist.objects.filter(id=int(pid), owner=request.user).first()
    if not pl:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    pl.name = name
    pl.save(update_fields=["name"])
    return JsonResponse({"ok": True, "name": pl.name})


def _reorder_from_full_order(request):
    """Apply a complete drag-and-drop ordering.

    Only ids that genuinely belong to the caller's playlist are honoured —
    the id list arrives from the browser, so a crafted request must not be
    able to touch another user's rows or smuggle in foreign ids.
    """
    import json

    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "reason": "invalid_json"}, status=400)

    raw_ids = payload.get("order")
    if not isinstance(raw_ids, list) or not raw_ids:
        return JsonResponse({"ok": False, "reason": "invalid_params"}, status=400)

    try:
        ordered_ids = [int(value) for value in raw_ids]
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "reason": "invalid_params"}, status=400)

    owned = {
        item.id: item
        for item in PlaylistItem.objects.filter(
            id__in=ordered_ids, playlist__owner=request.user
        ).select_related("playlist")
    }
    if not owned:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    # Every id must belong to the same playlist; a mixed list is either a
    # bug or an attempt to reshuffle something else at the same time.
    playlist_ids = {item.playlist_id for item in owned.values()}
    if len(playlist_ids) != 1 or len(owned) != len(set(ordered_ids)):
        return JsonResponse({"ok": False, "reason": "invalid_params"}, status=400)

    with transaction.atomic():
        for position, item_id in enumerate(ordered_ids, start=1):
            PlaylistItem.objects.filter(pk=item_id).update(order=position)

    return JsonResponse({"ok": True, "moved": True, "count": len(ordered_ids)})


@require_POST
@login_required
def api_playlist_reorder(request):
    """Reorder a playlist, in either of the two shapes the UI produces.

    1. Whole order (drag-and-drop): a JSON body {"order": [item_id, ...]}.
    2. One step (the up/down arrows, which are what touch and keyboard
       users get): form fields playlist_id + item_id + direction.

    Both end in the same place — orders re-sequenced 1..N — so the two
    input paths cannot drift into different results.
    """
    if request.content_type == "application/json":
        return _reorder_from_full_order(request)

    pid = request.POST.get("playlist_id")
    item_id = request.POST.get("item_id")
    direction = request.POST.get("direction")

    if not pid or not str(pid).isdigit() or not item_id or not str(item_id).isdigit():
        return JsonResponse({"ok": False, "reason": "invalid_params"}, status=400)
    if direction not in ("up", "down"):
        return JsonResponse({"ok": False, "reason": "invalid_direction"}, status=400)

    pl = Playlist.objects.filter(id=int(pid), owner=request.user).first()
    if not pl:
        return JsonResponse({"ok": False, "reason": "not_found"}, status=404)

    items = list(PlaylistItem.objects.filter(playlist=pl).order_by("order", "-created_at"))
    ids = [it.id for it in items]
    try:
        idx = ids.index(int(item_id))
    except ValueError:
        return JsonResponse({"ok": False, "reason": "item_not_found"}, status=404)

    target = idx - 1 if direction == "up" else idx + 1
    if target < 0 or target >= len(items):
        return JsonResponse({"ok": True, "moved": False})

    # Re-sequence orders 1..N from the swapped list so ties never recur.
    items[idx], items[target] = items[target], items[idx]
    with transaction.atomic():
        for i, it in enumerate(items, start=1):
            PlaylistItem.objects.filter(pk=it.pk).update(order=i)

    return JsonResponse({"ok": True, "moved": True})


@login_required
def api_playlist_mine(request):
    qs = (
        Playlist.objects.filter(owner=request.user)
        .annotate(item_count=Count("items"))
        .order_by("-created_at")[:200]
        .values("id", "name", "item_count")
    )
    return JsonResponse({"ok": True, "playlists": list(qs)})
