from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.db.models import Count
from tracks.models import Track
from interactions.models import TrackLike
from .models import Playlist, PlaylistItem


@login_required
def library_view(request):
    playlists = Playlist.objects.filter(owner=request.user).order_by("-created_at")

    liked_track_ids = (
        TrackLike.objects.filter(user=request.user)
        .order_by("-created_at")
        .values_list("track_id", flat=True)[:200]
    )
    liked_tracks = (
        Track.objects.filter(id__in=list(liked_track_ids), status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        .select_related("creator")
        .prefetch_related("genres")
    )

    return render(request, "library/library.html", {
        "playlists": playlists,
        "liked_tracks": liked_tracks,
    })


@login_required
def playlist_detail(request, playlist_id: int):
    pl = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    items = (
        PlaylistItem.objects.filter(playlist=pl)
        .select_related("track", "track__creator")
        .prefetch_related("track__genres")
        .order_by("-created_at")
    )
    return render(request, "playlists/playlist_detail.html", {"pl": pl, "items": items})


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
            PlaylistItem.objects.create(playlist=pl, track=track)
            added = True
    except IntegrityError:
        PlaylistItem.objects.filter(playlist=pl, track=track).delete()
        added = False

    count = PlaylistItem.objects.filter(playlist=pl).count()
    return JsonResponse({"ok": True, "added": added, "count": count})




@login_required
def api_playlist_mine(request):
    qs = (
        Playlist.objects.filter(owner=request.user)
        .annotate(item_count=Count("items"))
        .order_by("-created_at")[:200]
        .values("id", "name", "item_count")
    )
    return JsonResponse({"ok": True, "playlists": list(qs)})
