#!/bin/sh
set -e

# Wait for PostgreSQL, then migrate under a cluster-wide advisory lock so
# concurrent container starts (for example `compose up` racing a
# `compose run` one-off) cannot run migrations against the same database at
# the same time. Deployments that migrate as an explicit release step can
# set MIGRATE_ON_START=0.
python - <<'PY'
import os
import subprocess
import sys
import time

MIGRATE = os.environ.get("MIGRATE_ON_START", "1") == "1"

if os.environ.get("USE_SQLITE", "0") == "1":
    if MIGRATE:
        subprocess.run([sys.executable, "manage.py", "migrate", "--no-input"], check=True)
    sys.exit(0)

import psycopg

dsn = (
    f"host={os.environ.get('DB_HOST', 'localhost')} "
    f"port={os.environ.get('DB_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'orders')} "
    f"user={os.environ.get('POSTGRES_USER', 'orders')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', 'dev-only-password')}"
)
deadline = time.monotonic() + 60
while True:
    try:
        connection = psycopg.connect(dsn, connect_timeout=3, autocommit=True)
        break
    except Exception as exc:
        if time.monotonic() > deadline:
            print(f"database never became ready: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)

try:
    if MIGRATE:
        # Session-level lock: held until released or the session ends, so a
        # crashed migration cannot leave the lock stuck.
        connection.execute("SELECT pg_advisory_lock(715001)")
        try:
            subprocess.run(
                [sys.executable, "manage.py", "migrate", "--no-input"], check=True
            )
        finally:
            connection.execute("SELECT pg_advisory_unlock(715001)")
finally:
    connection.close()
PY

exec "$@"
