from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse


class OnboardingRequiredMiddleware:
    """Redirect authenticated users to onboarding until they complete profile.

    This keeps the UX consistent: first login -> profile setup -> then explore.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            path = request.path or ""

            # Allow-list paths that should remain accessible before onboarding.
            allow_prefixes = (
                "/admin/",
                "/static/",
                "/media/",
                "/login/",
                "/logout/",
                "/register/",
                "/phone/",
                "/phone/verify/",
                "/onboarding/",
                "/google/",
                "/creator/apply/",
                "/accounts/phone/",
                "/accounts/phone/verify/",
                "/accounts/onboarding/",
            )
            if path.startswith(allow_prefixes):
                return self.get_response(request)

            # Some deployments may add allauth later.
            if path.startswith("/accounts/"):
                return self.get_response(request)

            profile = getattr(user, "profile", None)
            if profile is not None:
                if not getattr(profile, "phone_verified_at", None):
                    return redirect(reverse("phone_start"))
                if not getattr(profile, "onboarding_complete", False):
                    return redirect(reverse("onboarding"))

        return self.get_response(request)
