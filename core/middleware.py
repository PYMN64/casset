from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Minimal security headers.

    Kept conservative to avoid breaking existing inline scripts/styles.
    You can tighten CSP later once you remove inline code.
    """

    def process_response(self, request, response):
        # Basic hardening
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        # Minimal CSP (allow self). If you rely on inline scripts, you may need 'unsafe-inline' temporarily.
        # We keep scripts/styles permissive enough for templates+app.js.
        csp = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';"
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
