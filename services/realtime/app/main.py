"""FastAPI realtime gateway.

Why a separate async service instead of doing WebSockets in Django: the core
service is synchronous WSGI, one worker per in-flight request, which is the
wrong shape for thousands of mostly idle, long-lived connections. This
process holds them all on a single event loop and needs nothing but a LISTEN
connection to Postgres; it does no queries and keeps no state, so it can be
scaled horizontally behind a load balancer without coordination.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.manager import Client, ConnectionManager
from app.settings import Settings


class EventSource(Protocol):
    connected: bool
    last_error: str | None

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


SourceFactory = Callable[[Settings, Callable[[dict[str, Any]], None]], EventSource]


def _postgres_source(settings: Settings, on_event: Callable[[dict[str, Any]], None]) -> EventSource:
    from app.events import PostgresEventSource

    return PostgresEventSource(
        dsn=settings.database_url,
        channels=[settings.order_channel, settings.stock_channel],
        on_event=on_event,
        max_backoff_seconds=settings.reconnect_max_backoff_seconds,
    )


def create_app(source_factory: SourceFactory = _postgres_source) -> FastAPI:
    settings = Settings()
    logging.basicConfig(level=settings.log_level.upper())
    manager = ConnectionManager(queue_size=settings.client_queue_size)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        source = source_factory(settings, manager.broadcast)
        await source.start()
        app.state.source = source
        yield
        await source.stop()

    app = FastAPI(title="realtime-orders gateway", lifespan=lifespan)
    app.state.manager = manager
    app.state.settings = settings

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        source: EventSource = app.state.source
        healthy = source.connected
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ok" if healthy else "degraded",
                "pg_listener": source.connected,
                "last_error": source.last_error,
                "clients": manager.client_count,
                "dropped_messages": manager.total_dropped,
            },
        )

    @app.websocket("/ws/dashboard")
    async def ws_dashboard(websocket: WebSocket) -> None:
        await _serve(websocket, manager, settings, order_filter=None)

    @app.websocket("/ws/orders/{public_id}")
    async def ws_order(websocket: WebSocket, public_id: str) -> None:
        await _serve(websocket, manager, settings, order_filter=public_id)

    return app


async def _serve(
    websocket: WebSocket,
    manager: ConnectionManager,
    settings: Settings,
    order_filter: str | None,
) -> None:
    await websocket.accept()
    client = manager.register(order_filter)
    await websocket.send_text(
        json.dumps(
            {
                "type": "hello",
                "filter": order_filter,
                "server_time": datetime.now(UTC).isoformat(),
            }
        )
    )
    sender = asyncio.create_task(_pump(websocket, client, settings.heartbeat_seconds))
    try:
        # We never act on inbound frames; receiving is how disconnects surface.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        manager.unregister(client)


async def _pump(websocket: WebSocket, client: Client, heartbeat_seconds: float) -> None:
    while True:
        try:
            message = await asyncio.wait_for(client.queue.get(), timeout=heartbeat_seconds)
        except TimeoutError:
            await websocket.send_text('{"type": "heartbeat"}')
            continue
        await websocket.send_text(message)


app = create_app()
