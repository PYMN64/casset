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
