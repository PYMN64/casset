from django.urls import path

from . import views

urlpatterns = [
    path("upload/", views.upload_track, name="upload_track"),
    path("my/tracks/", views.my_tracks, name="my_tracks"),
    path("my/tracks/<int:track_id>/edit/", views.edit_track, name="edit_track"),
    path("my/tracks/<int:track_id>/submit/", views.submit_track, name="submit_track"),
    path("my/tracks/<int:track_id>/toggle-visibility/", views.toggle_track_visibility, name="toggle_track_visibility"),
]
