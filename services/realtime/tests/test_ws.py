"""WebSocket endpoint tests using an injected fake event source, so the full
accept → hello → fan-out → filter behaviour is exercised without PostgreSQL."""

import asyncio
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


class FakeEventSource:
    def __init__(self, on_event: Callable[[dict], None]) -> None:
        self._on_event = on_event
        self._loop: asyncio.AbstractEventLoop | None = None
        self.connected = True
        self.last_error: str | None = None
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def emit(self, payload: dict) -> None:
        """Deliver an event from the test thread onto the app's event loop,
        the same marshalling a real NOTIFY callback gets from asyncpg."""
        assert self._loop is not None, "emit() before lifespan startup"
        self._loop.call_soon_threadsafe(self._on_event, payload)


@pytest.fixture
def fake_app():
    sources: list[FakeEventSource] = []

    def factory(settings: Settings, on_event: Callable[[dict], None]) -> FakeEventSource:
        source = FakeEventSource(on_event)
        sources.append(source)
        return source

    app = create_app(source_factory=factory)
    return app, sources


def test_lifespan_starts_and_stops_the_source(fake_app):
    app, sources = fake_app
    with TestClient(app):
        assert sources[0].started
        assert not sources[0].stopped
    assert sources[0].stopped


def test_dashboard_receives_order_and_stock_events(fake_app):
    app, sources = fake_app
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["filter"] is None

        sources[0].emit({"type": "order", "order_id": "abc", "status": "PENDING"})
        sources[0].emit({"type": "stock", "warehouse": "LDN", "changes": []})

        assert ws.receive_json()["type"] == "order"
        assert ws.receive_json()["type"] == "stock"


def test_order_socket_only_sees_its_own_order(fake_app):
    app, sources = fake_app
    with TestClient(app) as client, client.websocket_connect("/ws/orders/abc") as ws:
        assert ws.receive_json()["filter"] == "abc"

        sources[0].emit({"type": "order", "order_id": "zzz", "status": "PENDING"})
        sources[0].emit({"type": "stock", "warehouse": "LDN", "changes": []})
        sources[0].emit({"type": "order", "order_id": "abc", "status": "SHIPPED"})

        # The first frame through must already be the matching order; the
        # mismatched order and the stock event were filtered out.
        message = ws.receive_json()
        assert (message["order_id"], message["status"]) == ("abc", "SHIPPED")


def test_heartbeat_keeps_idle_sockets_warm(fake_app, monkeypatch):
    monkeypatch.setenv("RT_HEARTBEAT_SECONDS", "0.05")
    sources: list[FakeEventSource] = []

    def factory(settings: Settings, on_event: Callable[[dict], None]) -> FakeEventSource:
        source = FakeEventSource(on_event)
        sources.append(source)
        return source

    app = create_app(source_factory=factory)
    with TestClient(app) as client, client.websocket_connect("/ws/dashboard") as ws:
        ws.receive_json()  # hello
        assert ws.receive_json() == {"type": "heartbeat"}


def test_healthz_reflects_listener_state(fake_app):
    app, sources = fake_app
    with TestClient(app) as client:
        healthy = client.get("/healthz")
        assert healthy.status_code == 200
        assert healthy.json()["pg_listener"] is True

        sources[0].connected = False
        sources[0].last_error = "ConnectionResetError: simulated"
        degraded = client.get("/healthz")
        assert degraded.status_code == 503
        assert degraded.json()["status"] == "degraded"
        assert "simulated" in degraded.json()["last_error"]
