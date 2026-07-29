# Contributing / development guide

## Prerequisites

Docker Desktop (or engine + compose). For fast local iteration without
Docker: Python 3.13 and Node 22.

## Full stack

```bash
cp .env.example .env
docker compose up -d --build        # db, redis, core (auto-migrates), realtime
docker compose run --rm core python manage.py seed_data
docker compose --profile ui up -d   # + Vue dev server on :5173
docker compose run --rm core python manage.py demo_orders   # live traffic
```

Dashboard: http://localhost:5173 · API: http://localhost:8000/api/ ·
Admin: http://localhost:8000/admin/ · Realtime health: http://localhost:8001/healthz

## Tests

| What | Command |
|---|---|
| Everything, inside containers | `make test` |
| Core quick loop (SQLite, no Docker) | `cd services/core && USE_SQLITE=1 pytest -m "not integration"` |
| Core full (needs Postgres up) | `cd services/core && DB_HOST=localhost pytest` |
| Realtime | `cd services/realtime && pytest -m "not integration"` |
| Pickpath (reference + parity where built) | `pytest native/pickpath/tests` |
| Frontend | `cd frontend && npm test && npm run typecheck` |

Integration-marked tests require PostgreSQL semantics (row locks,
LISTEN/NOTIFY) and skip themselves on SQLite rather than pass vacuously.

Pytest loads `config.settings_test`, which supplies a throwaway secret key
and then defers to the real `config.settings`. That is why the suite runs
with no environment configured even though the service itself refuses to
start without an explicit `DJANGO_SECRET_KEY` when debug is off.

## The browser demo

The dashboard published to GitHub Pages is the same build with its event
source swapped for an in-browser simulation, because Pages cannot run
Django, FastAPI and PostgreSQL. Run it locally with:

```bash
cd frontend && npm run dev:replay     # or: npm run build:replay
```

`src/demo/` holds the whole of it, reached only through `api.ts` and
`composables/useDemoReplay.ts`, so no component knows it exists. Two rules
if you touch it:

- **Keep it out of the real bundle.** The engine is constructed lazily on
  purpose. A module-level instance is a side effect that stops Rollup
  dropping the module, and the simulator then ships inside the production
  image. If `npm run build` grows by about 7 kB, that has happened again.
- **Keep it honest.** It emits the same frames `orders/events.py` publishes,
  and the pick-path port in `src/demo/pickpath.ts` copies the reference
  implementation's tie-breaking so the routes match the real engines. If the
  event contract changes, this changes with it.

## Style

- Python: `ruff check .` and `ruff format .` (config in `ruff.toml`), mypy
  per-service (`services/*/pyproject.toml`). `pre-commit install` wires the
  hooks.
- TypeScript: strict `vue-tsc`; keep components presentational and state in
  the Pinia store.
- Language: prose, comments and docs use British English. Code identifiers
  keep ecosystem spellings (Django's `serializers`, `optimize_route`) so
  they stay consistent with the APIs they touch.
- Commits: conventional style (`feat:`, `fix:`, `ci:`, `docs:` ...), present
  tense, body explains the *why*.

## Architecture changes

Significant decisions get an ADR in `docs/adr/` (see the four existing ones
for the shape). If a change alters the event payload contract between the
services, update `orders/events.py`, both services' tests, and
`frontend/src/types.ts` together.
