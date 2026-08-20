from __future__ import annotations


class SecurityHeadersMiddleware:
    """Security headers applied to every response.

    CSP notes
    ---------
    The policy is `self`-only for every fetch directive. That is possible
    because Casset has no third-party assets at all: the font is
    self-hosted (static/css/fonts.css), Chart.js is vendored
    (static/vendor/), and the icon set is inline SVG. An external font CDN
    used to be referenced from base.html and was silently blocked by this
    very policy — the font never loaded in any browser. Keep it that way:
    if you find yourself widening this policy for an asset, host the asset
    instead.

    `'unsafe-inline'` remains on script-src and style-src because a few
    templates still carry small inline blocks (the pre-paint theme script,
    per-page chart configuration). Those are the last things standing
    between this policy and a nonce-based one.

    `frame-ancestors 'none'` blocks clickjacking site-wide; the embed page
    opts out of X-Frame-Options separately via @xframe_options_exempt and
    is served under its own relaxed policy below.
    """

    #: Paths that are meant to be iframed by third parties.
    EMBED_PREFIXES = ("/embed/",)

    BASE_CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        path = request.path or ""
        if path.startswith(self.EMBED_PREFIXES):
            # The embed player exists to be framed by other sites, so it
            # gets everything except the ancestor restriction.
            csp = self.BASE_CSP
        else:
            csp = self.BASE_CSP + "; frame-ancestors 'none'"
        h.setdefault("Content-Security-Policy", csp)
        return response
