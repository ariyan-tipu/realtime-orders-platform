"""Concurrency-correctness tests.

These fire genuinely simultaneous transactions from multiple threads (each
thread gets its own database connection) against one PostgreSQL database, and
assert the invariants that row-level locking is supposed to protect:

1. stock never oversells, no matter how many buyers race for it;
2. pk-ordered lock acquisition prevents lock-ordering deadlocks;
3. units are conserved when placements race cancellations.

They are skipped on SQLite because SQLite's SELECT FOR UPDATE is a no-op;
passing there would prove nothing.
"""

import threading

import pytest
from django.db import connection

from inventory.models import Stock
from orders.models import Order, OrderItem, OrderStatus
from orders.services import InsufficientStock, OrderLine, advance_order, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


def run_in_threads(workers: list) -> list:
    """Start every worker behind a barrier so they hit the database together;
    collect ("ok", value) / ("insufficient", exc) / ("error", exc) per worker."""
    barrier = threading.Barrier(len(workers), timeout=15)
    results: list = [None] * len(workers)

    def runner(index: int, fn) -> None:
        try:
            barrier.wait()
            results[index] = ("ok", fn())
        except InsufficientStock as exc:
            results[index] = ("insufficient", exc)
        except Exception as exc:  # noqa: BLE001 - surfaced via assertions below
            results[index] = ("error", exc)
        finally:
            connection.close()  # each thread opened its own connection

    threads = [
        threading.Thread(target=runner, args=(index, fn)) for index, fn in enumerate(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "worker deadlocked or hung"
    return results


def test_concurrent_placements_never_oversell():
    """Eight buyers race for five units: exactly five succeed, stock ends at
    zero, and it never goes negative. This is the race that SELECT FOR UPDATE
    exists to prevent; without it, several buyers read quantity=5
    simultaneously and all decrement."""
    warehouse = make_warehouse()
    variant = make_variant(sku="HOT-1")
    make_stock(variant, warehouse, quantity=5)
    user = make_user()

    def buy():
        return place_order(
            user=user, warehouse=warehouse, lines=[OrderLine(variant_id=variant.id, quantity=1)]
        )

    results = run_in_threads([buy] * 8)

    errors = [r for r in results if r[0] == "error"]
    assert not errors, f"unexpected failures: {errors}"
    assert sum(1 for r in results if r[0] == "ok") == 5
    assert sum(1 for r in results if r[0] == "insufficient") == 3

    stock = Stock.objects.get(variant=variant)
    assert stock.quantity == 0
    assert Order.objects.count() == 5
    units_sold = sum(OrderItem.objects.filter(variant=variant).values_list("quantity", flat=True))
    assert units_sold == 5


def test_opposite_item_orderings_do_not_deadlock():
    """Thread 1 orders [A, B]; thread 2 orders [B, A], repeatedly. With naive
    lock-in-request-order this interleaving deadlocks; pk-ordered locking makes
    both threads acquire A-then-B (or B-then-A) consistently, so it cannot."""
    warehouse = make_warehouse()
    variant_a = make_variant(sku="LOCK-A")
    variant_b = make_variant(sku="LOCK-B")
    make_stock(variant_a, warehouse, quantity=100)
    make_stock(variant_b, warehouse, quantity=100)
    user = make_user()

    def buy_many(variant_ids: list[int], rounds: int = 10):
        placed = []
        for _ in range(rounds):
            placed.append(
                place_order(
                    user=user,
                    warehouse=warehouse,
                    lines=[OrderLine(variant_id=vid, quantity=1) for vid in variant_ids],
                )
            )
        return placed

    results = run_in_threads(
        [
            lambda: buy_many([variant_a.id, variant_b.id]),
            lambda: buy_many([variant_b.id, variant_a.id]),
        ]
    )

    errors = [r for r in results if r[0] != "ok"]
    assert not errors, f"deadlock or failure: {errors}"
    assert Stock.objects.get(variant=variant_a).quantity == 80
    assert Stock.objects.get(variant=variant_b).quantity == 80


def test_racing_placements_and_cancellations_conserve_units():
    """Placements and cancellations race on the same stock row; whatever the
    interleaving, units must be conserved:
    final stock + units held by non-cancelled orders == initial stock."""
    warehouse = make_warehouse()
    variant = make_variant(sku="MIX-1")
    make_stock(variant, warehouse, quantity=50)
    user = make_user()

    to_cancel = [
        place_order(
            user=user, warehouse=warehouse, lines=[OrderLine(variant_id=variant.id, quantity=2)]
        )
        for _ in range(6)
    ]
    assert Stock.objects.get(variant=variant).quantity == 38

    def cancel(order: Order):
        return lambda: advance_order(order.pk, OrderStatus.CANCELLED)

    def buy():
        return place_order(
            user=user, warehouse=warehouse, lines=[OrderLine(variant_id=variant.id, quantity=3)]
        )

    results = run_in_threads([cancel(order) for order in to_cancel] + [buy] * 6)
    errors = [r for r in results if r[0] == "error"]
    assert not errors, f"unexpected failures: {errors}"

    final_stock = Stock.objects.get(variant=variant).quantity
    held_by_active_orders = sum(
        OrderItem.objects.filter(variant=variant)
        .exclude(order__status=OrderStatus.CANCELLED)
        .values_list("quantity", flat=True)
    )
    assert final_stock + held_by_active_orders == 50
    assert final_stock >= 0
