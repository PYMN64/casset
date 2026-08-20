from django.urls import path

from core import staff_views

app_name = "staff"

urlpatterns = [
    path("", staff_views.platform_dashboard, name="platform_dashboard"),
    path("users/", staff_views.users_console, name="users_console"),
    path("creators/", staff_views.creators_console, name="creators_console"),
    path("creators/<int:user_id>/", staff_views.creator_detail, name="creator_detail"),
    path("creators/<int:user_id>/toggle-verified/", staff_views.toggle_verified, name="toggle_verified"),
]
