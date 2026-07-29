# ADR 0002: Postgres LISTEN/NOTIFY for order events; Redis stays a cache

**Status:** accepted

## Context

The core service must tell the realtime service about order and stock
changes. Candidates: poll the database (wasteful and laggy), publish to
Redis pub/sub, or use PostgreSQL's built-in LISTEN/NOTIFY.

The subtle failure mode with an external broker is the dual write: the
database transaction commits, then the process publishes to Redis. Crash
between the two and the event is lost; publish before commit and
subscribers can see an order that was rolled back. Fixing this properly
means an outbox table and a relay, which is real machinery, justified at
scale and overkill here.

## Decision

Emit events with `pg_notify(...)` on the same connection, inside the same
transaction as the data change. PostgreSQL queues notifications
transactionally: they are delivered only on commit and dropped on rollback.
The integration test `test_rolled_back_transaction_emits_nothing` pins this
guarantee.

Redis remains in the stack for what it is genuinely good at here: caching
the hot analytics aggregation (30s TTL) so the dashboard's polling of
`/api/analytics/top-sellers/` does not re-run a three-join window query it
just ran.

## Consequences

- Exactly-when-committed delivery with zero extra infrastructure and no
  ordering ambiguity relative to the data.
- Known limits, accepted deliberately: NOTIFY payloads are capped (about
  8 KB; ours are a few hundred bytes); delivery is at-most-once to
  currently connected listeners (a realtime replica that is down misses
  events, which is fine because dashboards re-hydrate a snapshot over REST
  on connect); throughput tops out far below a dedicated broker (irrelevant
  at this system's scale).
- If requirements grew to durable fan-out or cross-database consumers, the
  upgrade path is an outbox table plus Kafka or Redis Streams; the emit
  call sites would not change.
