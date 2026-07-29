"""End-to-end smoke test for a running stack.

Proves the full loop with real network traffic: a WebSocket subscriber sees
the order event emitted by a REST-placed order, and the pick-path endpoint
returns a valid route for it.

Usage (defaults match docker compose / local dev):
    python scripts/smoke_e2e.py [--api http://localhost:8000] [--ws ws://localhost:8001]

Dependencies: httpx, websockets (both present in services/realtime dev deps).
Exits 0 on success, 1 with a reason on failure. DEMO_MODE must be on.
"""

import argparse
import asyncio
import json
import sys

import httpx
import websockets

TIMEOUT_SECONDS = 10.0


async def run(api_base: str, ws_base: str) -> None:
    async with httpx.AsyncClient(base_url=api_base, timeout=TIMEOUT_SECONDS) as api:
        core_health = (await api.get("/healthz")).json()
        assert core_health["database"], f"core reports unhealthy database: {core_health}"
        print(f"[1/6] core healthy: {core_health}")

        async with websockets.connect(f"{ws_base}/ws/dashboard") as socket:
            hello = json.loads(await asyncio.wait_for(socket.recv(), TIMEOUT_SECONDS))
            assert hello["type"] == "hello", f"expected hello frame, got {hello}"
            print(f"[2/6] websocket subscribed: {hello}")

            placed = await api.post("/api/demo/orders/")
            assert placed.status_code in (200, 201), f"demo order failed: {placed.text}"
            body = placed.json()
            assert body["placed"], f"nothing placed: {body}"
            order_id = body["placed"]["public_id"]
            print(f"[3/6] order placed over REST: {order_id}")

            # The commit must surface as a WebSocket event (stock events and
            # demo advances may arrive first).
            deadline = asyncio.get_running_loop().time() + TIMEOUT_SECONDS
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                assert remaining > 0, "timed out waiting for the order event"
                event = json.loads(await asyncio.wait_for(socket.recv(), remaining))
                if event.get("type") == "order" and event.get("order_id") == order_id:
                    break
            assert event["status"] == "PENDING", f"unexpected first status: {event}"
            print(f"[4/6] order event received on the socket: {event['order_id']} PENDING")

        path = (await api.get(f"/api/orders/{order_id}/pick-path/")).json()
        assert path["stops"], f"pick path has no stops: {path}"
        assert path["total_distance"] >= 0, f"negative distance: {path}"
        print(
            f"[5/6] pick path computed by {path['engine']} engine: "
            f"{len(path['stops'])} stops, distance {path['total_distance']}, "
            f"{path['computed_ms']} ms"
        )

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as raw:
        rt_url = ws_base.replace("ws://", "http://").replace("wss://", "https://")
        rt_health = (await raw.get(f"{rt_url}/healthz")).json()
        assert rt_health["pg_listener"], f"realtime listener down: {rt_health}"
        print(f"[6/6] realtime healthy: {rt_health}")

    print("SMOKE TEST PASSED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--ws", default="ws://localhost:8001")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.api, args.ws))
    except AssertionError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
