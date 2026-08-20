from django.urls import path

from . import views

urlpatterns = [
    path("tracks/", views.track_list, name="track_list"),
    # uslug, not slug: track slugs are generated with allow_unicode=True, so
    # Persian titles produce non-ASCII slugs the built-in converter rejects.
    path("t/<uslug:slug>/", views.track_detail, name="track_detail"),
    path("artist/<str:username>/", views.artist_profile, name="artist_profile"),
    path("download/<int:track_id>/", views.download_track, name="download_track"),
    # Album management (creator-facing)
    path("albums/", views.album_list, name="album_list"),
    path("albums/create/", views.album_create, name="album_create"),
    path("albums/<int:album_id>/edit/", views.album_edit, name="album_edit"),
    path("albums/<int:album_id>/delete/", views.album_delete, name="album_delete"),
]
