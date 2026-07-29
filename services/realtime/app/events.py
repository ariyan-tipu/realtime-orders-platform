"""PostgreSQL LISTEN-based event source with automatic reconnection.

One dedicated asyncpg connection LISTENs on the order/stock channels. The
core service emits NOTIFY inside its transactions, so everything arriving
here corresponds to a committed change. If the connection drops, the source
reconnects with capped exponential backoff and reports its health so
/healthz can expose a degraded state instead of failing silently.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

OnEvent = Callable[[dict[str, Any]], None]

_KEEPALIVE_SECONDS = 5.0


class PostgresEventSource:
    def __init__(
        self,
        dsn: str,
        channels: list[str],
        on_event: OnEvent,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self._dsn = dsn
        self._channels = channels
        self._on_event = on_event
        self._max_backoff = max_backoff_seconds
        self._task: asyncio.Task[None] | None = None
        self.connected = False
        self.last_error: str | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="pg-event-source")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self.connected = False

    async def _run(self) -> None:
        backoff = 1.0
        while True:
            connection: asyncpg.Connection | None = None
            try:
                connection = await asyncpg.connect(self._dsn)
                for channel in self._channels:
                    await connection.add_listener(channel, self._handle)
                self.connected = True
                self.last_error = None
                backoff = 1.0
                logger.info("listening on %s", ", ".join(self._channels))
                # NOTIFY delivery is push-based; this loop only exists to
                # detect dead links promptly via a cheap keepalive query.
                while True:
                    await asyncio.sleep(_KEEPALIVE_SECONDS)
                    await connection.execute("SELECT 1")
            except asyncio.CancelledError:
                if connection is not None:
                    with contextlib.suppress(Exception):
                        await connection.close()
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("event source disconnected (%s); retrying in %.1fs", exc, backoff)
                if connection is not None:
                    with contextlib.suppress(Exception):
                        await connection.close()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._max_backoff)

    def _handle(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("malformed NOTIFY payload on %s: %.200s", channel, payload)
            return
        self._on_event(data)
