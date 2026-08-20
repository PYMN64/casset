from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class OnboardingRequiredMiddleware:
    """Redirect authenticated users to onboarding until they complete profile.

    This keeps the UX consistent: first login -> profile setup -> then explore.

    IMPORTANT: API endpoints are never redirected. A browser redirect in
    response to an XHR/fetch call breaks the caller (the JS gets HTML where
    it expected JSON). API paths get a 403 JSON payload instead, so the
    frontend can react properly.
    """

    # Paths that stay reachable before onboarding is finished.
    ALLOW_PREFIXES = (
        "/admin/",
        "/static/",
        "/media/",
        "/login/",
        "/logout/",
        "/register/",
        "/phone/",
        "/onboarding/",
        "/google/",
        "/creator/apply/",
        "/accounts/",
        "/account/phone/",
        "/terms/",
        "/privacy/",
        "/healthz/",
    )

    # API paths: never redirect, return JSON instead.
    API_PREFIXES = ("/api/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return self.get_response(request)

        path = request.path or ""

        if path.startswith(self.ALLOW_PREFIXES):
            return self.get_response(request)

        profile = getattr(user, "profile", None)
        onboarded = bool(getattr(profile, "onboarding_complete", False)) if profile else True
        if onboarded:
            return self.get_response(request)

        # Not onboarded past this point.
        if path.startswith(self.API_PREFIXES):
            return JsonResponse(
                {
                    "ok": False,
                    "error": "onboarding_required",
                    "detail": "برای استفاده از این بخش، ابتدا پروفایل خود را کامل کنید.",
                    "redirect": reverse("onboarding"),
                },
                status=403,
            )

        return redirect(reverse("onboarding"))
