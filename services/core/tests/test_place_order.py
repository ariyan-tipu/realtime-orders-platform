import pytest

from inventory.models import Stock
from orders.models import Order, OrderItem, OrderStatus, OrderStatusEvent
from orders.services import InsufficientStock, OrderLine, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = pytest.mark.django_db


@pytest.fixture
def warehouse():
    return make_warehouse()


@pytest.fixture
def user():
    return make_user()


def test_placement_decrements_stock_and_snapshots_price(user, warehouse):
    variant = make_variant(sku="MUG-1", price_pence=799)
    make_stock(variant, warehouse, quantity=10)

    order = place_order(
        user=user, warehouse=warehouse, lines=[OrderLine(variant_id=variant.id, quantity=3)]
    )

    assert order.status == OrderStatus.PENDING
    assert order.total_pence == 3 * 799
    stock = Stock.objects.get(variant=variant, warehouse=warehouse)
    assert stock.quantity == 7

    item = order.items.get()
    assert item.unit_price_pence == 799
    assert item.line_total_pence == 3 * 799

    # Catalogue price changes must not rewrite history.
    variant.price_pence = 9999
    variant.save()
    item.refresh_from_db()
    assert item.unit_price_pence == 799


def test_multi_line_order_totals(user, warehouse):
    cheap = make_variant(sku="PEN-1", price_pence=250)
    dear = make_variant(sku="BAG-1", price_pence=4500)
    make_stock(cheap, warehouse, quantity=10)
    make_stock(dear, warehouse, quantity=10)

    order = place_order(
        user=user,
        warehouse=warehouse,
        lines=[
            OrderLine(variant_id=cheap.id, quantity=4),
            OrderLine(variant_id=dear.id, quantity=1),
        ],
    )
    assert order.total_pence == 4 * 250 + 4500
    assert order.items.count() == 2


def test_insufficient_stock_rolls_back_everything(user, warehouse):
    available = make_variant(sku="OK-1", price_pence=100)
    scarce = make_variant(sku="LOW-1", price_pence=100)
    make_stock(available, warehouse, quantity=10)
    make_stock(scarce, warehouse, quantity=1)

    with pytest.raises(InsufficientStock) as excinfo:
        place_order(
            user=user,
            warehouse=warehouse,
            lines=[
                OrderLine(variant_id=available.id, quantity=2),
                OrderLine(variant_id=scarce.id, quantity=5),
            ],
        )

    shortage = excinfo.value.shortages[0]
    assert (shortage.sku, shortage.requested, shortage.available) == ("LOW-1", 5, 1)

    # All-or-nothing: the satisfiable line must not have been applied either.
    assert Stock.objects.get(variant=available).quantity == 10
    assert Stock.objects.get(variant=scarce).quantity == 1
    assert Order.objects.count() == 0
    assert OrderItem.objects.count() == 0
    assert OrderStatusEvent.objects.count() == 0


def test_variant_without_stock_row_reports_zero_available(user, warehouse):
    unstocked = make_variant(sku="GHOST-1")

    with pytest.raises(InsufficientStock) as excinfo:
        place_order(
            user=user,
            warehouse=warehouse,
            lines=[OrderLine(variant_id=unstocked.id, quantity=1)],
        )
    assert excinfo.value.shortages[0].available == 0


def test_placement_creates_audit_event(user, warehouse):
    variant = make_variant()
    make_stock(variant, warehouse, quantity=5)
    order = place_order(
        user=user, warehouse=warehouse, lines=[OrderLine(variant_id=variant.id, quantity=1)]
    )
    event = order.status_events.get()
    assert event.from_status is None
    assert event.to_status == OrderStatus.PENDING


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([], "at least one line"),
        ([OrderLine(variant_id=1, quantity=0)], ">= 1"),
        ([OrderLine(variant_id=1, quantity=1), OrderLine(variant_id=1, quantity=2)], "duplicate"),
    ],
)
def test_invalid_input_rejected(user, warehouse, lines, message):
    with pytest.raises(ValueError, match=message):
        place_order(user=user, warehouse=warehouse, lines=lines)


def test_unknown_variant_rejected(user, warehouse):
    with pytest.raises(ValueError, match="unknown variant"):
        place_order(user=user, warehouse=warehouse, lines=[OrderLine(variant_id=99999, quantity=1)])
