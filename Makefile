# Convenience targets for the Docker workflow. On Windows without make,
# run the underlying `docker compose ...` commands directly (see README).

.PHONY: help up down logs migrate seed demo test test-unit lint fmt bench explain psql

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up: ## Start the full stack (db, redis, core, realtime)
	docker compose up -d --build

down: ## Stop everything and free resources
	docker compose down

logs: ## Tail service logs
	docker compose logs -f core realtime

migrate: ## Apply database migrations
	docker compose run --rm core python manage.py migrate

seed: ## Seed demo catalog, stock and order history
	docker compose run --rm core python manage.py seed_data

demo: ## Continuously place & advance orders to drive the live dashboard
	docker compose run --rm core python manage.py demo_orders

test: ## Full test suite (unit + integration + concurrency) inside containers
	docker compose run --rm core pytest
	docker compose run --rm realtime pytest

test-unit: ## Fast unit tests only (no database required)
	docker compose run --rm -e USE_SQLITE=1 core pytest -m "not integration"

lint: ## Ruff lint + format check + mypy
	docker compose run --rm core sh -c "ruff check . && ruff format --check ."
	docker compose run --rm core mypy .
	docker compose run --rm realtime mypy .

fmt: ## Auto-format Python
	docker compose run --rm core ruff format .

bench: ## Benchmark C++ pick-path engine vs pure Python
	docker compose run --rm core python /opt/bench_pickpath.py

explain: ## Print EXPLAIN ANALYZE report for the top-sellers query
	docker compose run --rm core python manage.py explain_report

psql: ## Open a psql shell on the dev database
	docker compose exec db psql -U $${POSTGRES_USER:-orders} -d $${POSTGRES_DB:-orders}
