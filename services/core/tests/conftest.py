import pytest
from django.core.cache import cache
from django.db import connection


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Integration tests need real PostgreSQL semantics (SELECT FOR UPDATE,
    LISTEN/NOTIFY). On SQLite they would silently pass without testing
    anything, so they are skipped instead."""
    if connection.vendor == "postgresql":
        return
    skip = pytest.mark.skip(reason="requires PostgreSQL; run via docker compose or CI")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()
