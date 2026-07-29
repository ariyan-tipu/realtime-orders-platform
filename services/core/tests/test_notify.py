"""LISTEN/NOTIFY integration tests.

A second, autocommit psycopg connection LISTENs on the event channels while
the service layer commits (or rolls back) transactions. This proves the core
delivery guarantee the realtime service depends on: events are delivered
exactly when a transaction commits, and never for a rolled-back one.
"""

import json
import time

import psycopg
import pytest
from django.db import connection

from orders.events import ORDER_CHANNEL, STOCK_CHANNEL
from orders.services import InsufficientStock, OrderLine, place_order
from tests.factories import make_stock, make_user, make_variant, make_warehouse

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def listener():
    settings_dict = connection.settings_dict  # the *test* database, not the dev one
    conn = psycopg.connect(
        host=settings_dict["HOST"],
        port=settings_dict["PORT"],
        dbname=settings_dict["NAME"],
        user=settings_dict["USER"],
        password=settings_dict["PASSWORD"],
        autocommit=True,
    )
    conn.execute(f"LISTEN {ORDER_CHANNEL}")
    conn.execute(f"LISTEN {STOCK_CHANNEL}")
    yield conn
    conn.close()


def collect_notifications(conn: psycopg.Connection, window_seconds: float) -> list:
    received = []
    deadline = time.monotonic() + window_seconds
    while (remaining := deadline - time.monotonic()) > 0:
        for notification in conn.notifies(timeout=remaining, stop_after=1):
            received.append(notification)
    return received


def test_commit_delivers_order_and_stock_events(listener):
    warehouse = make_warehouse()
    variant = make_variant(sku="EVT-1")
    make_stock(variant, warehouse, quantity=5)

    order = place_order(
        user=make_user(),
        warehouse=warehouse,
        lines=[OrderLine(variant_id=variant.id, quantity=2)],
    )

    received = collect_notifications(listener, window_seconds=5)
    by_channel = {n.channel: json.loads(n.payload) for n in received}

    assert set(by_channel) == {ORDER_CHANNEL, STOCK_CHANNEL}
    order_event = by_channel[ORDER_CHANNEL]
    assert order_event["order_id"] == str(order.public_id)
    assert order_event["status"] == "PENDING"
    assert order_event["previous"] is None
    stock_event = by_channel[STOCK_CHANNEL]
    assert stock_event["changes"] == [
        {"sku": "EVT-1", "product": variant.product.name, "quantity": 3, "bin": [3, 4]}
    ]


def test_rolled_back_transaction_emits_nothing(listener):
    """The event is queued inside the same transaction as the stock change, so
    a rollback (here: an oversell) must suppress it entirely. An after-the-fact
    publish to an external broker cannot make this guarantee."""
    warehouse = make_warehouse()
    variant = make_variant(sku="EVT-2")
    make_stock(variant, warehouse, quantity=1)

    with pytest.raises(InsufficientStock):
        place_order(
            user=make_user(),
            warehouse=warehouse,
            lines=[OrderLine(variant_id=variant.id, quantity=99)],
        )

    assert collect_notifications(listener, window_seconds=1.5) == []
