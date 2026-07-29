"""Realtime event emission via PostgreSQL NOTIFY.

Design note: pg_notify is called on the *same connection, inside the same
transaction* as the data change. PostgreSQL queues the notification and
delivers it only if the transaction commits, so subscribers can never observe
an event for a rolled-back order, and there is no dual-write race like the one
you accept when publishing to an external broker after commit.
See docs/adr/0002-postgres-listen-notify-for-events.md for the trade-offs
against Redis pub/sub.
"""

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.db import connection

if TYPE_CHECKING:
    from inventory.models import Stock, Warehouse
    from orders.models import Order

ORDER_CHANNEL = "order_events"
STOCK_CHANNEL = "stock_events"


def _notify(channel: str, payload: dict) -> None:
    if connection.vendor != "postgresql":
        return  # unit-test / SQLite environments have no realtime plane
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_notify(%s, %s)", [channel, json.dumps(payload, default=str)])


def emit_order_event(order: "Order", previous: str | None, items_count: int) -> None:
    _notify(
        ORDER_CHANNEL,
        {
            "type": "order",
            "order_id": str(order.public_id),
            "status": order.status,
            "previous": previous,
            "warehouse": order.warehouse.code,
            "total_pence": order.total_pence,
            "currency": order.currency,
            "items_count": items_count,
            "created_at": order.created_at.isoformat(),
        },
    )


def emit_stock_events(warehouse: "Warehouse", stocks: Iterable["Stock"]) -> None:
    changes = [
        {
            "sku": stock.variant.sku,
            "product": stock.variant.product.name,
            "quantity": stock.quantity,
            "bin": [stock.bin_x, stock.bin_y],
        }
        for stock in stocks
    ]
    if changes:
        _notify(STOCK_CHANNEL, {"type": "stock", "warehouse": warehouse.code, "changes": changes})
