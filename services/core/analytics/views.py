from datetime import timedelta
from functools import cache as memoize
from pathlib import Path

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

QUERIES_DIR = Path(__file__).resolve().parent / "queries"


@memoize
def load_query(name: str) -> str:
    return (QUERIES_DIR / f"{name}.sql").read_text()


def top_sellers(hours: int, limit: int) -> list[dict[str, object]]:
    since = timezone.now() - timedelta(hours=hours)
    with connection.cursor() as cursor:
        cursor.execute(load_query("top_sellers"), [since, limit])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


class TopSellersView(APIView):
    """Best-selling products per warehouse, cached briefly in Redis.

    The query itself is deliberately non-trivial (three joins, grouped
    aggregation, a window function) and index-supported; a 30s cache bounds
    staleness while keeping the dashboard from re-running it on every poll.
    """

    CACHE_TTL_SECONDS = 30

    def get(self, request: Request) -> Response:
        hours = self._int_param(request, "hours", default=24, lo=1, hi=24 * 7)
        limit = self._int_param(request, "limit", default=5, lo=1, hi=20)

        cache_key = f"analytics:top-sellers:{hours}:{limit}"
        payload = cache.get(cache_key)
        cache_hit = payload is not None
        if payload is None:
            payload = {
                "generated_at": timezone.now().isoformat(),
                "window_hours": hours,
                "top_n": limit,
                "rows": top_sellers(hours, limit),
            }
            cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        return Response({**payload, "cache_hit": cache_hit})

    @staticmethod
    def _int_param(request: Request, name: str, *, default: int, lo: int, hi: int) -> int:
        raw = request.query_params.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValidationError({name: "must be an integer"}) from exc
        if not lo <= value <= hi:
            raise ValidationError({name: f"must be between {lo} and {hi}"})
        return value
