"""Business logic for order placement and lifecycle transitions.

Every code path that mutates stock goes through this module so all of them
follow the same locking protocol:

- Stock rows are locked with SELECT ... FOR UPDATE **ordered by primary key**.
  Any two transactions needing overlapping rows acquire locks in the same
  global order, which makes lock-ordering deadlocks impossible.
- Status transitions first lock the Order row, then (for cancellations) stock
  rows: a strict order-then-stock hierarchy, never the reverse.

The concurrency tests in tests/test_concurrency.py exercise this protocol with
genuinely simultaneous transactions.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from catalog.models import ProductVariant
from inventory.models import Stock, Warehouse
from orders.events import emit_order_event, emit_stock_events
from orders.models import ORDER_STATUS_FLOW, Order, OrderItem, OrderStatus, OrderStatusEvent


@dataclass(frozen=True, slots=True)
class OrderLine:
    variant_id: int
    quantity: int


@dataclass(frozen=True, slots=True)
class Shortage:
    sku: str
    requested: int
    available: int


class OrderError(Exception):
    """Base class for order domain errors."""


class InsufficientStock(OrderError):
    def __init__(self, shortages: list[Shortage]) -> None:
        self.shortages = shortages
        detail = ", ".join(
            f"{s.sku} (requested {s.requested}, available {s.available})" for s in shortages
        )
        super().__init__(f"insufficient stock: {detail}")


class InvalidTransition(OrderError):
    def __init__(self, from_status: str, to_status: str) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"cannot transition {from_status} -> {to_status}")


def place_order(*, user: User, warehouse: Warehouse, lines: Sequence[OrderLine]) -> Order:
    """Atomically place an order, decrementing stock exactly once.

    All-or-nothing: if any line cannot be fully satisfied the whole
    transaction rolls back and InsufficientStock reports every shortage.
    """
    if not lines:
        raise ValueError("an order needs at least one line")
    if any(line.quantity < 1 for line in lines):
        raise ValueError("line quantities must be >= 1")
    variant_ids = [line.variant_id for line in lines]
    if len(set(variant_ids)) != len(variant_ids):
        raise ValueError("duplicate variants in order lines; merge them first")

    variants = ProductVariant.objects.in_bulk(variant_ids)
    unknown = set(variant_ids) - variants.keys()
    if unknown:
        raise ValueError(f"unknown variant ids: {sorted(unknown)}")

    with transaction.atomic():
        # of=("self",) locks only the stock rows, not the joined variant rows.
        locked = list(
            Stock.objects.select_for_update(of=("self",))
            .select_related("variant__product")
            .filter(warehouse=warehouse, variant_id__in=variant_ids)
            .order_by("pk")
        )
        stock_by_variant = {stock.variant_id: stock for stock in locked}

        shortages = []
        for line in lines:
            stock = stock_by_variant.get(line.variant_id)
            available = stock.quantity if stock else 0
            if available < line.quantity:
                shortages.append(
                    Shortage(
                        sku=variants[line.variant_id].sku,
                        requested=line.quantity,
                        available=available,
                    )
                )
        if shortages:
            # atomic() rolls back on raise; row locks release with the transaction.
            raise InsufficientStock(shortages)

        now = timezone.now()
        for line in lines:
            stock = stock_by_variant[line.variant_id]
            stock.quantity -= line.quantity
            stock.updated_at = now
        Stock.objects.bulk_update(locked, ["quantity", "updated_at"])

        total = sum(line.quantity * variants[line.variant_id].price_pence for line in lines)
        order = Order.objects.create(
            user=user, warehouse=warehouse, status=OrderStatus.PENDING, total_pence=total
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                variant_id=line.variant_id,
                quantity=line.quantity,
                unit_price_pence=variants[line.variant_id].price_pence,
            )
            for line in lines
        )
        OrderStatusEvent.objects.create(
            order=order, from_status=None, to_status=OrderStatus.PENDING, note="order placed"
        )

        emit_order_event(order, previous=None, items_count=len(lines))
        emit_stock_events(warehouse, locked)
    return order


def advance_order(order: Order | int, to_status: str, note: str = "") -> Order:
    """Apply one lifecycle transition; cancelling restocks the items.

    The Order row is locked first so concurrent transitions on the same order
    serialise; without this, two racing CONFIRM requests would both read
    PENDING and both "succeed".
    """
    order_pk = order.pk if isinstance(order, Order) else order
    with transaction.atomic():
        locked_order = (
            Order.objects.select_for_update(of=("self",))
            .select_related("warehouse")
            .get(pk=order_pk)
        )
        if to_status not in ORDER_STATUS_FLOW[locked_order.status]:
            raise InvalidTransition(locked_order.status, to_status)

        previous = locked_order.status
        items = list(locked_order.items.all())
        restocked: list[Stock] = []
        if to_status == OrderStatus.CANCELLED:
            restocked = _restock(locked_order, items)

        locked_order.status = to_status
        locked_order.save(update_fields=["status", "updated_at"])
        OrderStatusEvent.objects.create(
            order=locked_order, from_status=previous, to_status=to_status, note=note
        )

        emit_order_event(locked_order, previous=previous, items_count=len(items))
        if restocked:
            emit_stock_events(locked_order.warehouse, restocked)
    return locked_order


def _restock(order: Order, items: list[OrderItem]) -> list[Stock]:
    """Return cancelled items to stock under the same pk-ordered lock protocol."""
    variant_ids = [item.variant_id for item in items]
    locked = list(
        Stock.objects.select_for_update(of=("self",))
        .select_related("variant__product")
        .filter(warehouse=order.warehouse, variant_id__in=variant_ids)
        .order_by("pk")
    )
    stock_by_variant = {stock.variant_id: stock for stock in locked}
    now = timezone.now()
    recreated: list[Stock] = []
    for item in items:
        stock = stock_by_variant.get(item.variant_id)
        if stock is None:
            # Stock row removed since placement (e.g. delisted variant):
            # recreate it at the depot so the units are not lost.
            recreated.append(
                Stock.objects.create(
                    variant_id=item.variant_id,
                    warehouse=order.warehouse,
                    quantity=item.quantity,
                    bin_x=0,
                    bin_y=0,
                )
            )
        else:
            stock.quantity += item.quantity
            stock.updated_at = now
    Stock.objects.bulk_update(locked, ["quantity", "updated_at"])
    return locked + recreated
