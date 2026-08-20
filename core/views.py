"""Public, unauthenticated core views — currently just the health check."""

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Liveness/readiness probe for a load balancer or uptime monitor.

    Checks the two stateful dependencies a request actually needs (DB,
    cache) rather than just returning 200 unconditionally — a health check
    that can't detect a dead DB connection isn't worth having.
    """
    checks = {}
    healthy = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        cache_key = "healthz:probe"
        cache.set(cache_key, "1", timeout=5)
        checks["cache"] = "ok" if cache.get(cache_key) == "1" else "error: readback mismatch"
    except Exception as exc:
        checks["cache"] = f"error: {exc}"
        healthy = False

    status_code = 200 if healthy else 503
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=status_code,
    )


def robots_txt(request):
    """robots.txt, generated rather than a static file.

    The Sitemap: line has to carry the live host — hardcoding it in a
    static file breaks the moment the site is served from a staging
    domain, and a wrong sitemap URL is worse than none.

    The Disallow list is the set of routes that are either private or
    infinite (search result permutations), which are the two things that
    waste crawl budget on a media site.
    """
    from django.http import HttpResponse

    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /staff/",
        "Disallow: /settings/",
        "Disallow: /dashboard/",
        "Disallow: /upload/",
        "Disallow: /my/",
        "Disallow: /onboarding/",
        "Disallow: /creator/",
        "Disallow: /account/",
        "Disallow: /api/",
        "Disallow: /search/",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /phone/",
        "Disallow: /google/",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
