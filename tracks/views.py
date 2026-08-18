from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from .models import Track, Genre, Album
from .forms import AlbumForm
from accounts.models import UserProfile





def track_list(request):
    genre_slug = request.GET.get("genre")
    album_id = request.GET.get("album")
    qs = Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC).select_related("creator").prefetch_related("genres")

    active_genre = None
    if genre_slug:
        active_genre = get_object_or_404(Genre, slug=genre_slug)
        qs = qs.filter(genres=active_genre)

    active_album = None
    if album_id:
        active_album = get_object_or_404(Album, id=album_id)
        qs = qs.filter(album=active_album)

    genres = Genre.objects.all()
    return render(request, "tracks/track_list.html", {
        "tracks": qs[:50],
        "genres": genres,
        "active_genre": active_genre,
        "active_album": active_album,
    })


def track_detail(request, slug):
    qs = Track.objects.select_related("creator").prefetch_related("genres")
    track = get_object_or_404(qs, slug=slug)
    # Access control: public/unlisted approved OR owner
    if track.creator_id != getattr(request.user, "id", None):
        if track.status != Track.Status.APPROVED:
            raise Http404
        if track.visibility == Track.Visibility.PRIVATE:
            raise Http404
    return render(request, "tracks/track_detail.html", {"track": track})


def artist_profile(request, username):
    """Legacy route kept for compatibility.

    New canonical profile URL is /@<username>/
    """
    return redirect('public_profile', username=username)

@login_required
def download_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, status=Track.Status.APPROVED)
    if track.visibility == Track.Visibility.PRIVATE and track.creator_id != request.user.id:
        raise Http404
    if not track.audio:
        raise Http404

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.has_vip():
        raise Http404  # یا redirect به /vip/

    # فایل لوکال: FileResponse
    return FileResponse(track.audio.open("rb"), as_attachment=True, filename=f"{track.slug}.mp3")


@login_required
def album_list(request):
    """List the current user's albums (creator-facing management page)."""
    # annotate track_count to avoid N+1 in template (a.tracks.count per row)
    from django.db.models import Count
    albums = (
        Album.objects
        .filter(creator=request.user)
        .annotate(track_count=Count("tracks"))
        .order_by("-created_at")
    )
    return render(request, "tracks/albums.html", {"albums": albums})


@login_required
def album_create(request):
    if request.method == "POST":
        form = AlbumForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            album = form.save(commit=False)
            album.creator = request.user
            album.save()
            messages.success(request, "آلبوم ساخته شد.")
            return redirect("album_list")
    else:
        form = AlbumForm(user=request.user)
    return render(request, "tracks/album_create.html", {"form": form, "is_edit": False})


@login_required
def album_edit(request, album_id: int):
    album = get_object_or_404(Album, id=album_id, creator=request.user)
    if request.method == "POST":
        form = AlbumForm(request.POST, request.FILES, instance=album, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "تغییرات آلبوم ذخیره شد.")
            return redirect("album_list")
    else:
        form = AlbumForm(instance=album, user=request.user)
    return render(request, "tracks/album_create.html", {"form": form, "is_edit": True, "album": album})


@login_required
@require_POST
def album_delete(request, album_id: int):
    """Delete an album owned by the current user.

    Only accepts POST (enforced by @require_POST) to prevent accidental
    deletion via GET (e.g. a crawler or prefetch following links).
    Tracks inside the album are NOT deleted — their `album` FK is set to
    NULL (on_delete=SET_NULL on Track.album), so they remain intact.
    """
    album = get_object_or_404(Album, id=album_id, creator=request.user)
    title = album.title
    album.delete()
    messages.success(request, f"آلبوم «{title}» حذف شد. ترک‌های داخل آن دست‌نخورده باقی ماندند.")
    return redirect("album_list")
