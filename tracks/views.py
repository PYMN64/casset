from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from accounts.models import UserProfile

from .forms import AlbumForm
from .models import Album, Genre, Track


@xframe_options_exempt
def track_embed(request, slug):
    """Minimal standalone player page for <iframe> embedding on external
    sites — see templates/tracks/embed.html (does not extend base.html:
    no nav/sidebar/playerbar, just the one track's player). Same visibility
    rule as track_detail; an embed of a private track must 404 too.

    @xframe_options_exempt tells django.middleware.clickjacking's
    XFrameOptionsMiddleware to skip adding X-Frame-Options: DENY on this
    response — that project-wide default would otherwise block the exact
    use case this view exists for (being framed by someone else's site).
    """
    qs = Track.objects.select_related("creator").prefetch_related("genres")
    track = get_object_or_404(qs, slug=slug)
    if track.status != Track.Status.APPROVED or track.visibility == Track.Visibility.PRIVATE:
        raise Http404
    return render(request, "tracks/embed.html", {"track": track})


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

    from django.db.models import Count

    comments = (
        track.comments.filter(is_public=True)
        .select_related("author")
        .annotate(like_count=Count("likes"))
        .order_by("-created_at")[:100]
    )

    is_favorited = False
    is_reposted = False
    can_download = False
    if request.user.is_authenticated:
        is_favorited = track.favorited_by.filter(user=request.user).exists()
        is_reposted = track.reposts.filter(user=request.user).exists()
        # Regression fix: this context key was referenced by the template's
        # {% if can_download %} but never set, so the download button (and
        # the whole point of the VIP download_track view) never rendered.
        can_download = bool(track.audio) and request.user.profile.has_vip()

    return render(request, "tracks/track_detail.html", {
        "track": track,
        "comments": comments,
        "comment_count": track.comments.filter(is_public=True).count(),
        "favorite_count": track.favorited_by.count(),
        "is_favorited": is_favorited,
        "repost_count": track.reposts.count(),
        "is_reposted": is_reposted,
        "can_download": can_download,
    })


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


def show_detail(request, album_id: int):
    """Public page for an Album acting as a podcast/music "show" — episode
    list + (for podcasts) the RSS subscribe link real podcast apps need.
    Owner can always see it (to grab the RSS link before going fully
    public); everyone else needs is_public=True."""
    album = get_object_or_404(Album.objects.select_related("creator"), id=album_id)
    if not album.is_public and album.creator_id != getattr(request.user, "id", None):
        raise Http404

    episodes = (
        Track.objects.filter(
            album=album, status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )
        .select_related("creator")
        .order_by("-published_at")
    )
    return render(request, "tracks/show_detail.html", {"album": album, "episodes": episodes})


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
