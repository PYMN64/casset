from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from .models import Genre, Track


def track_list(request):
    genre_slug = request.GET.get("genre")
    qs = (
        Track.objects.filter(status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
        .select_related("creator")
        .prefetch_related("genres")
    )

    active_genre = None
    if genre_slug:
        active_genre = get_object_or_404(Genre, slug=genre_slug, is_active=True)
        qs = qs.filter(genres=active_genre)

    genres = Genre.objects.filter(is_active=True).order_by("content_type", "order", "name_fa")
    return render(
        request,
        "tracks/track_list.html",
        {
            "tracks": qs[:50],
            "genres": genres,
            "active_genre": active_genre,
        },
    )


def track_detail(request, slug):
    qs = Track.objects.select_related("creator").prefetch_related("genres")
    track = get_object_or_404(qs, slug=slug)

    if track.creator_id != getattr(request.user, "id", None):
        if track.status != Track.Status.APPROVED:
            raise Http404
        if track.visibility == Track.Visibility.PRIVATE:
            raise Http404

    can_download = False
    if request.user.is_authenticated and track.audio:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        can_download = profile.has_vip()

    return render(
        request,
        "tracks/track_detail.html",
        {"track": track, "can_download": can_download},
    )


def artist_profile(request, username):
    return redirect("public_profile", username=username)


@login_required
def download_track(request, track_id: int):
    track = get_object_or_404(Track, id=track_id, status=Track.Status.APPROVED)
    if track.visibility == Track.Visibility.PRIVATE and track.creator_id != request.user.id:
        raise Http404
    if not track.audio:
        raise Http404

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.has_vip():
        raise Http404

    return FileResponse(track.audio.open("rb"), as_attachment=True, filename=f"{track.slug}.mp3")
