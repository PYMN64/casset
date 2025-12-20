from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from .models import Track, Genre
from accounts.models import UserProfile





def track_list(request):
    genre_slug = request.GET.get("genre")
    qs = Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC).select_related("creator").prefetch_related("genres")

    active_genre = None
    if genre_slug:
        active_genre = get_object_or_404(Genre, slug=genre_slug)
        qs = qs.filter(genres=active_genre)

    genres = Genre.objects.all()
    return render(request, "tracks/track_list.html", {
        "tracks": qs[:50],
        "genres": genres,
        "active_genre": active_genre,
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
