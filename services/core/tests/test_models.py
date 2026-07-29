import pytest
from django.db import IntegrityError

from orders.models import OrderItem
from orders.services import OrderLine, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = pytest.mark.django_db


def test_sku_is_unique():
    make_variant(sku="DUP-1")
    with pytest.raises(IntegrityError):
        make_variant(sku="DUP-1")


def test_one_stock_row_per_variant_per_warehouse():
    warehouse = make_warehouse()
    variant = make_variant()
    make_stock(variant, warehouse)
    with pytest.raises(IntegrityError):
        make_stock(variant, warehouse)


def test_order_item_quantity_check_constraint():
    warehouse = make_warehouse()
    variant = make_variant()
    make_stock(variant, warehouse, quantity=5)
    order = place_order(
        user=make_user(),
        warehouse=warehouse,
        lines=[OrderLine(variant_id=variant.id, quantity=1)],
    )
    with pytest.raises(IntegrityError):
        OrderItem.objects.create(order=order, variant=variant, quantity=0, unit_price_pence=100)


def test_orders_have_distinct_public_ids():
    warehouse = make_warehouse()
    variant = make_variant()
    make_stock(variant, warehouse, quantity=5)
    user = make_user()
    lines = [OrderLine(variant_id=variant.id, quantity=1)]
    first = place_order(user=user, warehouse=warehouse, lines=lines)
    second = place_order(user=user, warehouse=warehouse, lines=lines)
    assert first.public_id != second.public_id
