from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse


def healthz(request: HttpRequest) -> JsonResponse:
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception:  # pragma: no cover - only trips when infrastructure is down
        pass
    try:
        cache.set("healthz", "ok", 5)
        checks["cache"] = cache.get("healthz") == "ok"
    except Exception:  # pragma: no cover
        pass
    status = 200 if all(checks.values()) else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", **checks}, status=status)
