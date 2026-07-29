"""Print EXPLAIN ANALYZE plans for the top-sellers query, with and without
its supporting index.

Methodology matters here:
- `VACUUM (ANALYZE)` runs first, so the planner has current statistics and
  the visibility map is populated (index-only scans are impossible without
  it on a freshly bulk-loaded table).
- Each variant is executed twice and the second run is reported, so both
  variants are measured against warm caches rather than whichever ran first
  paying the cold-start cost.
- PostgreSQL DDL is transactional, so the "without index" measurement drops
  the index inside a transaction that is rolled back; the live schema is
  never actually changed and both variants see identical data.

Output is markdown-ready for docs/query-optimisation.md.
"""

import re
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.utils import timezone

from analytics.views import load_query

INDEX_NAME = "order_active_created_idx"


class Command(BaseCommand):
    help = "EXPLAIN ANALYZE report for the top-sellers query (PostgreSQL only)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("EXPLAIN ANALYZE report requires PostgreSQL")

        since = timezone.now() - timedelta(hours=options["hours"])
        params = [since, options["limit"]]
        sql = "EXPLAIN (ANALYZE, BUFFERS) " + load_query("top_sellers")

        self._print_dataset_stats(since)

        with connection.cursor() as cursor:
            cursor.execute("VACUUM (ANALYZE) orders_order, orders_orderitem")

        with_index = self._measure(sql, params)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'DROP INDEX "{INDEX_NAME}"')
            without_index = self._measure(sql, params)
            transaction.set_rollback(True)  # restore the index; nothing committed

        self.stdout.write(f"## With `{INDEX_NAME}`\n")
        self.stdout.write("```text")
        self.stdout.write(with_index)
        self.stdout.write("```\n")
        self.stdout.write(f"## Without `{INDEX_NAME}` (dropped in a rolled-back transaction)\n")
        self.stdout.write("```text")
        self.stdout.write(without_index)
        self.stdout.write("```\n")

        self.stdout.write("## Summary\n")
        self.stdout.write("| Variant | Execution time |")
        self.stdout.write("|---|---|")
        self.stdout.write(f"| With index | {self._execution_time(with_index)} |")
        self.stdout.write(f"| Without index | {self._execution_time(without_index)} |")

    def _print_dataset_stats(self, since: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM orders_order")
            total_orders = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM orders_order "
                "WHERE created_at >= %s AND status <> 'CANCELLED'",
                [since],
            )
            in_window = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM orders_orderitem")
            total_items = cursor.fetchone()[0]
        share = (in_window / total_orders * 100) if total_orders else 0
        self.stdout.write(
            f"Dataset: {total_orders} orders ({total_items} items); "
            f"{in_window} non-cancelled orders in the window ({share:.2f}%).\n"
        )

    @staticmethod
    def _measure(sql: str, params: list[Any]) -> str:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)  # warm-up: prime caches, discard plan
            cursor.fetchall()
            cursor.execute(sql, params)
            return "\n".join(row[0] for row in cursor.fetchall())

    @staticmethod
    def _execution_time(plan: str) -> str:
        match = re.search(r"Execution Time: ([\d.]+) ms", plan)
        return f"{match.group(1)} ms" if match else "n/a"
