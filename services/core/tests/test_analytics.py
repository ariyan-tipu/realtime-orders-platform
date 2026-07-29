from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.views import top_sellers
from orders.models import OrderStatus
from orders.services import OrderLine, advance_order, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = pytest.mark.django_db


@pytest.fixture
def sales_history():
    london = make_warehouse(code="LDN")
    manchester = make_warehouse(code="MCR")
    user = make_user()

    popular = make_variant(sku="POP-1", price_pence=1000)
    niche = make_variant(sku="NIC-1", price_pence=2000)
    for warehouse in (london, manchester):
        make_stock(popular, warehouse, quantity=500)
        make_stock(niche, warehouse, quantity=500)

    def order(variant, quantity, warehouse, *, age_hours=1, cancelled=False):
        placed = place_order(
            user=user,
            warehouse=warehouse,
            lines=[OrderLine(variant_id=variant.id, quantity=quantity)],
        )
        if cancelled:
            advance_order(placed, OrderStatus.CANCELLED)
        if age_hours:
            type(placed).objects.filter(pk=placed.pk).update(
                created_at=timezone.now() - timedelta(hours=age_hours)
            )
        return placed

    order(popular, 10, london)
    order(popular, 5, london)
    order(niche, 3, london)
    order(niche, 9, manchester)
    order(popular, 2, manchester)
    order(popular, 50, london, age_hours=30)  # outside the 24h window
    order(niche, 40, london, cancelled=True)  # cancelled: excluded

    return london, manchester, popular, niche


def test_top_sellers_ranks_per_warehouse_and_excludes_noise(sales_history):
    rows = top_sellers(hours=24, limit=5)
    by_warehouse: dict[str, list] = {}
    for row in rows:
        by_warehouse.setdefault(str(row["warehouse"]), []).append(row)

    ldn = by_warehouse["LDN"]
    assert [row["sales_rank"] for row in ldn] == [1, 2]
    assert ldn[0]["units_sold"] == 15  # 10 + 5, the 30h-old 50 excluded
    assert ldn[0]["revenue_pence"] == 15 * 1000
    assert ldn[1]["units_sold"] == 3  # cancelled 40 excluded

    mcr = by_warehouse["MCR"]
    assert mcr[0]["units_sold"] == 9
    assert mcr[0]["sales_rank"] == 1


def test_top_sellers_respects_limit(sales_history):
    rows = top_sellers(hours=24, limit=1)
    assert all(row["sales_rank"] == 1 for row in rows)


def test_endpoint_caches_result(sales_history):
    client = APIClient()
    first = client.get("/api/analytics/top-sellers/")
    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert len(first.json()["rows"]) > 0

    second = client.get("/api/analytics/top-sellers/")
    assert second.json()["cache_hit"] is True
    assert second.json()["rows"] == first.json()["rows"]


def test_endpoint_validates_params(sales_history):
    client = APIClient()
    assert client.get("/api/analytics/top-sellers/", {"hours": "nope"}).status_code == 400
    assert client.get("/api/analytics/top-sellers/", {"hours": "9999"}).status_code == 400
    assert client.get("/api/analytics/top-sellers/", {"limit": "0"}).status_code == 400
