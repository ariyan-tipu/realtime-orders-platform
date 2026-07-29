"""End-to-end over a real PostgreSQL: NOTIFY on the database side must come
out of the WebSocket on the other, through the real asyncpg listener."""

import asyncio
import json
import time

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
def dsn() -> str:
    dsn = Settings().database_url
    try:
        asyncio.run(_check(dsn))
    except OSError as exc:
        pytest.skip(f"PostgreSQL not reachable at {dsn}: {exc}")
    return dsn


async def _check(dsn: str) -> None:
    connection = await asyncpg.connect(dsn, timeout=3)
    await connection.close()


async def _notify(dsn: str, channel: str, payload: dict) -> None:
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute("SELECT pg_notify($1, $2)", channel, json.dumps(payload))
    finally:
        await connection.close()


def test_notify_reaches_websocket_subscriber(dsn):
    app = create_app()
    with TestClient(app) as client:
        deadline = time.monotonic() + 10
        while client.get("/healthz").status_code != 200:
            assert time.monotonic() < deadline, "listener never connected"
            time.sleep(0.2)

        with client.websocket_connect("/ws/dashboard") as ws:
            assert ws.receive_json()["type"] == "hello"

            event = {"type": "order", "order_id": "it-order-1", "status": "CONFIRMED"}
            asyncio.run(_notify(dsn, Settings().order_channel, event))

            assert ws.receive_json() == event
