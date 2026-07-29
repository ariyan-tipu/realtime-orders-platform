"""Randomised demo traffic, shared by the /api/demo endpoint and the
`demo_orders` management command. Everything goes through the real service
layer so demo traffic exercises the same locks and emits the same events as
production traffic would.
"""

import random

from django.contrib.auth.models import User

from inventory.models import Stock
from orders.models import ORDER_STATUS_FLOW, Order, OrderStatus
from orders.services import InvalidTransition, OrderLine, advance_order, place_order


def demo_user() -> User:
    user, _ = User.objects.get_or_create(
        username="demo-customer", defaults={"first_name": "Demo", "last_name": "Customer"}
    )
    return user


def place_random_order(rng: random.Random | None = None) -> Order | None:
    """Place an order for 1-3 random in-stock variants from one warehouse.

    Returns None when nothing is sellable. May raise InsufficientStock if it
    races another buyer; callers decide whether to resample.
    """
    rng = rng or random.Random()
    pool = list(
        Stock.objects.filter(quantity__gt=0, variant__is_active=True)
        .select_related("warehouse", "variant")
        .order_by("?")[:60]
    )
    if not pool:
        return None
    warehouse = pool[0].warehouse
    candidates = [stock for stock in pool if stock.warehouse_id == warehouse.id]
    picks = rng.sample(candidates, k=min(len(candidates), rng.randint(1, 3)))
    lines = [
        OrderLine(variant_id=stock.variant_id, quantity=rng.randint(1, min(2, stock.quantity)))
        for stock in picks
    ]
    return place_order(user=demo_user(), warehouse=warehouse, lines=lines)


def advance_random_orders(
    limit: int, cancel_rate: float = 0.15, rng: random.Random | None = None
) -> list[Order]:
    """Advance up to `limit` random non-terminal orders one lifecycle step."""
    rng = rng or random.Random()
    candidates = list(
        Order.objects.exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]).order_by(
            "-created_at"
        )[:50]
    )
    rng.shuffle(candidates)
    advanced: list[Order] = []
    for order in candidates[:limit]:
        next_statuses = ORDER_STATUS_FLOW[order.status]
        if not next_statuses:
            continue
        forward = sorted(next_statuses - {OrderStatus.CANCELLED})
        cancellable = OrderStatus.CANCELLED in next_statuses
        if cancellable and (not forward or rng.random() < cancel_rate):
            choice: str = OrderStatus.CANCELLED
        else:
            choice = forward[0]
        try:
            advanced.append(advance_order(order, choice, note="demo traffic"))
        except InvalidTransition:  # raced by a concurrent demo request; skip
            continue
    return advanced
