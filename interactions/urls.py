from django.urls import path
from .views import toggle_like, toggle_follow

urlpatterns = [
    path("api/v1/like/", toggle_like, name="api_like"),
    path("api/v1/follow/", toggle_follow, name="api_follow"),
]
