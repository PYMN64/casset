from django.urls import path

from . import views

urlpatterns = [
    path("api/v1/play/", views.register_play, name="api_play"),
    path("api/v1/play/progress/", views.register_progress, name="api_play_progress"),
    path("api/v1/creator/stats/", views.api_creator_stats, name="api_creator_stats"),
]
