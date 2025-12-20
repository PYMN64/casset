from django.urls import path
from . import views

urlpatterns = [
    path("tracks/", views.track_list, name="track_list"),
    path("t/<slug:slug>/", views.track_detail, name="track_detail"),
    path("artist/<str:username>/", views.artist_profile, name="artist_profile"),
    path("download/<int:track_id>/", views.download_track, name="download_track"),
]
