import pytest

from inventory.models import Stock
from orders.models import OrderStatus
from orders.services import InvalidTransition, OrderLine, advance_order, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = pytest.mark.django_db


@pytest.fixture
def order_setup():
    warehouse = make_warehouse()
    variant = make_variant(price_pence=500)
    make_stock(variant, warehouse, quantity=10)
    order = place_order(
        user=make_user(),
        warehouse=warehouse,
        lines=[OrderLine(variant_id=variant.id, quantity=4)],
    )
    return order, variant, warehouse


def test_full_lifecycle_records_events(order_setup):
    order, _, _ = order_setup
    for target in [
        OrderStatus.CONFIRMED,
        OrderStatus.PICKING,
        OrderStatus.PACKED,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
    ]:
        order = advance_order(order, target)
    assert order.status == OrderStatus.DELIVERED

    transitions = list(order.status_events.values_list("from_status", "to_status"))
    assert transitions == [
        (None, "PENDING"),
        ("PENDING", "CONFIRMED"),
        ("CONFIRMED", "PICKING"),
        ("PICKING", "PACKED"),
        ("PACKED", "SHIPPED"),
        ("SHIPPED", "DELIVERED"),
    ]


def test_illegal_jump_rejected(order_setup):
    order, _, _ = order_setup
    with pytest.raises(InvalidTransition):
        advance_order(order, OrderStatus.PACKED)


def test_terminal_states_are_frozen(order_setup):
    order, _, _ = order_setup
    order = advance_order(order, OrderStatus.CANCELLED)
    with pytest.raises(InvalidTransition):
        advance_order(order, OrderStatus.CONFIRMED)


def test_cancel_restocks_items(order_setup):
    order, variant, warehouse = order_setup
    assert Stock.objects.get(variant=variant).quantity == 6

    advance_order(order, OrderStatus.CANCELLED, note="customer changed mind")

    assert Stock.objects.get(variant=variant).quantity == 10
    event = order.status_events.get(to_status=OrderStatus.CANCELLED)
    assert event.note == "customer changed mind"


def test_cancel_after_picking_started_is_rejected(order_setup):
    order, _, _ = order_setup
    order = advance_order(order, OrderStatus.CONFIRMED)
    order = advance_order(order, OrderStatus.PICKING)
    with pytest.raises(InvalidTransition):
        advance_order(order, OrderStatus.CANCELLED)


def test_cancel_recreates_deleted_stock_row(order_setup):
    order, variant, warehouse = order_setup
    Stock.objects.filter(variant=variant).delete()

    advance_order(order, OrderStatus.CANCELLED)

    recreated = Stock.objects.get(variant=variant, warehouse=warehouse)
    assert recreated.quantity == 4  # the cancelled units are not lost
