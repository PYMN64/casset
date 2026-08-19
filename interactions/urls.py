from django.urls import path

from .views import (
    comment_add,
    comment_delete,
    comment_like,
    toggle_favorite,
    toggle_follow,
    toggle_like,
)

urlpatterns = [
    path("api/v1/like/", toggle_like, name="api_like"),
    path("api/v1/follow/", toggle_follow, name="api_follow"),
    path("api/v1/comment/add/", comment_add, name="api_comment_add"),
    path("api/v1/comment/<int:comment_id>/delete/", comment_delete, name="api_comment_delete"),
    path("api/v1/comment/<int:comment_id>/like/", comment_like, name="api_comment_like"),
    path("api/v1/favorite/", toggle_favorite, name="api_favorite"),
]
