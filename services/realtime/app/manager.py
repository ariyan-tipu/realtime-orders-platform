"""Fan-out of database events to connected WebSocket clients.

Every client gets a bounded asyncio.Queue. Broadcast never blocks and never
lets one slow consumer affect the others: when a queue is full the oldest
message is dropped to make room (the dashboard only needs fresh state, so
newest-wins is the right loss policy) and the drop is counted for /healthz.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

Payload = dict[str, Any]


@dataclass(eq=False)  # identity semantics: two clients are never "equal"
class Client:
    queue: asyncio.Queue[str]
    # None = firehose (dashboard); otherwise only events for this order id.
    order_filter: str | None = None
    dropped: int = 0

    def wants(self, payload: Payload) -> bool:
        if self.order_filter is None:
            return True
        return payload.get("type") == "order" and payload.get("order_id") == self.order_filter


@dataclass
class ConnectionManager:
    queue_size: int = 100
    _clients: set[Client] = field(default_factory=set)

    def register(self, order_filter: str | None = None) -> Client:
        client = Client(queue=asyncio.Queue(maxsize=self.queue_size), order_filter=order_filter)
        self._clients.add(client)
        return client

    def unregister(self, client: Client) -> None:
        self._clients.discard(client)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def total_dropped(self) -> int:
        return sum(client.dropped for client in self._clients)

    def broadcast(self, payload: Payload) -> None:
        message = json.dumps(payload)
        for client in self._clients:
            if not client.wants(payload):
                continue
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                # Shed the oldest message; suppress the (sender-racing) empty case.
                with contextlib.suppress(asyncio.QueueEmpty):
                    client.queue.get_nowait()
                client.queue.put_nowait(message)
                client.dropped += 1
                if client.dropped == 1 or client.dropped % 100 == 0:
                    logger.warning("slow websocket consumer: dropped %d message(s)", client.dropped)
