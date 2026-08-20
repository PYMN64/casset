from django.urls import path

from . import views

urlpatterns = [
    # pages
    path("library/", views.library_view, name="library"),
    path("p/<int:playlist_id>/", views.playlist_detail, name="playlist_detail"),

    # api
    path("api/v1/playlist/create/", views.api_playlist_create, name="api_playlist_create"),
    path("api/v1/playlist/delete/", views.api_playlist_delete, name="api_playlist_delete"),
    path("api/v1/playlist/rename/", views.api_playlist_rename, name="api_playlist_rename"),
    path("api/v1/playlist/reorder/", views.api_playlist_reorder, name="api_playlist_reorder"),
    path("api/v1/playlist/toggle-track/", views.api_playlist_toggle_track, name="api_playlist_toggle_track"),
    path("api/v1/playlist/mine/", views.api_playlist_mine, name="api_playlist_mine"),
]
