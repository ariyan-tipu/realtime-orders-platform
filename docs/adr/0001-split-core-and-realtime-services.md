# ADR 0001: split the platform into a sync core service and an async realtime service

**Status:** accepted

## Context

The platform needs (a) transactional business logic (order placement, stock
accounting, lifecycle transitions) and (b) live status delivery to browsers
over long-lived WebSocket connections.

Django's synchronous WSGI model is excellent for (a): mature ORM,
transactions, admin, migrations. It is the wrong shape for (b): each WSGI
worker handles one in-flight request, so N connected dashboards would pin N
workers doing nothing but holding sockets open. Django Channels exists, but
it converts the whole deployment to ASGI and couples the WebSocket fleet to
the business-logic process, which means they can then only scale together.

## Decision

Two services:

- **core** (Django, WSGI/gunicorn) owns all state and every write path.
- **realtime** (FastAPI, uvicorn/asyncio) owns WebSocket connections only.
  It executes no queries and keeps no state; it re-broadcasts committed
  events it receives from PostgreSQL (ADR 0002).

## Consequences

- Each service scales on its own axis: core by CPU-bound worker count,
  realtime by connection count (a single event loop comfortably holds
  thousands of mostly idle sockets).
- The realtime service is stateless, so multiple replicas need no
  coordination; any replica can serve any subscriber.
- Cost: two deployables and a contract (the event payload schema) between
  them. The schema is defined in one place (`orders/events.py`) and covered
  by integration tests on both sides.
