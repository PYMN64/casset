from django.urls import path
from .views import (
    CassetLoginView,
    logout_view,
    register_view,
    public_profile,
    profile_legacy_redirect,
    settings_view,
    dashboard_view,
    phone_start_view,
    phone_verify_view,
    onboarding_view,
    creator_apply_view,
    creator_studio_view,
    creator_handle_view,
    google_login_placeholder,
)

urlpatterns = [
    path("login/", CassetLoginView.as_view(), name="login"),
    path("phone/", phone_start_view, name="phone_start"),
    path("phone/verify/", phone_verify_view, name="phone_verify"),
    path("google/", google_login_placeholder, name="google_login_placeholder"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("creator/apply/", creator_apply_view, name="creator_apply"),
    path("creator/handle/", creator_handle_view, name="creator_handle"),
    path("creator/studio/", creator_studio_view, name="creator_studio"),
    path("logout/", logout_view, name="logout"),

    path("register/", register_view, name="register"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("settings/", settings_view, name="settings"),
    # New public profile style: /@username/
    path("@<str:username>/", public_profile, name="public_profile"),
    # Legacy: /u/username/ -> redirect
    path("u/<str:username>/", profile_legacy_redirect, name="public_profile_legacy"),
]
