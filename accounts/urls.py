from django.urls import path

from .views import (
    CassetLoginView,
    creator_apply_view,
    creator_handle_view,
    creator_studio_view,
    dashboard_view,
    google_login_placeholder,
    logout_view,
    onboarding_view,
    phone_start_view,
    phone_verify_view,
    profile_legacy_redirect,
    public_profile,
    register_view,
    settings_view,
)

urlpatterns = [
    path("login/", CassetLoginView.as_view(), name="login"),
    path("phone/", phone_start_view, name="phone_start"),
    path("phone/verify/", phone_verify_view, name="phone_verify"),
    path("google/", google_login_placeholder, name="google_login"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("creator/apply/", creator_apply_view, name="creator_apply"),
    path("creator/handle/", creator_handle_view, name="creator_handle"),
    path("creator/studio/", creator_studio_view, name="creator_studio"),
    path("logout/", logout_view, name="logout"),
    path("accounts/logout/", logout_view, name="logout_alias"),

    path("register/", register_view, name="register"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("settings/", settings_view, name="settings"),
    # New public profile style: /@username/
    path("@<str:username>/", public_profile, name="public_profile"),
    # Legacy: /u/username/ -> redirect
    path("u/<str:username>/", profile_legacy_redirect, name="public_profile_legacy"),
]
