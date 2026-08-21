from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    CassetLoginView,
    account_phone_start,
    account_phone_verify,
    api_user_connections,
    creator_apply_view,
    creator_handle_view,
    creator_studio_view,
    dashboard_view,
    deactivate_account,
    google_callback,
    google_login_start,
    logout_view,
    onboarding_view,
    phone_start_view,
    phone_verify_view,
    profile_legacy_redirect,
    public_profile,
    register_view,
    resend_verification_email_view,
    settings_view,
    verify_email_view,
)

urlpatterns = [
    path("login/", CassetLoginView.as_view(), name="login"),
    path("phone/", phone_start_view, name="phone_start"),
    path("phone/verify/", phone_verify_view, name="phone_verify"),

    # Google sign-in. `google_login` keeps its historical name so the
    # onboarding middleware allow-list and any old link stay correct.
    path("google/", google_login_start, name="google_login"),
    path("google/callback/", google_callback, name="google_callback"),

    # Adding/verifying a phone number on an account that already exists —
    # the prerequisite for publishing (see UserProfile.can_publish).
    path("account/phone/", account_phone_start, name="account_phone_start"),
    path("account/phone/verify/", account_phone_verify, name="account_phone_verify"),

    path("onboarding/", onboarding_view, name="onboarding"),
    path("creator/apply/", creator_apply_view, name="creator_apply"),
    path("creator/handle/", creator_handle_view, name="creator_handle"),
    path("creator/studio/", creator_studio_view, name="creator_studio"),
    path("logout/", logout_view, name="logout"),
    path("accounts/logout/", logout_view, name="logout_alias"),

    # Password reset — Django's own implementation (token generation and
    # expiry are the part you must never hand-roll); only the templates and
    # the redirect targets are ours.
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url=reverse_lazy("settings"),
        ),
        name="password_change",
    ),

    path("register/", register_view, name="register"),
    path("verify-email/resend/", resend_verification_email_view, name="resend_verification_email"),
    path("verify-email/<uidb64>/<token>/", verify_email_view, name="verify_email"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("settings/", settings_view, name="settings"),
    path("settings/deactivate/", deactivate_account, name="deactivate_account"),
    path("api/v1/connections/<str:username>/", api_user_connections, name="api_user_connections"),
    # New public profile style: /@username/
    path("@<str:username>/", public_profile, name="public_profile"),
    # Legacy: /u/username/ -> redirect
    path("u/<str:username>/", profile_legacy_redirect, name="public_profile_legacy"),
]
