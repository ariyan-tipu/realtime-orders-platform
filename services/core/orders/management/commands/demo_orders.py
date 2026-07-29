"""Continuously place and advance orders through the real service layer so the
dashboard shows live activity. Ctrl+C to stop.
"""

import random
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from catalog.models import ProductVariant
from orders.demo import advance_random_orders, place_random_order
from orders.services import InsufficientStock


class Command(BaseCommand):
    help = "Generate live demo traffic (placements + status transitions)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--interval", type=float, default=1.5, help="Seconds between rounds")
        parser.add_argument("--count", type=int, default=0, help="Rounds to run (0 = forever)")
        parser.add_argument("--cancel-rate", type=float, default=0.15)
        parser.add_argument("--seed", type=int, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        if not ProductVariant.objects.exists():
            raise CommandError("No catalogue found. Run `manage.py seed_data` first.")

        rng = random.Random(options["seed"])
        rounds = 0
        self.stdout.write("Generating demo traffic (Ctrl+C to stop)...")
        try:
            while True:
                self._round(rng, options["cancel_rate"])
                rounds += 1
                if options["count"] and rounds >= options["count"]:
                    break
                time.sleep(options["interval"] * rng.uniform(0.6, 1.4))
        except KeyboardInterrupt:
            self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Stopped after {rounds} rounds."))

    def _round(self, rng: random.Random, cancel_rate: float) -> None:
        try:
            order = place_random_order(rng)
            if order is None:
                self.stdout.write(self.style.WARNING("  no sellable stock; skipping placement"))
            else:
                self.stdout.write(
                    f"  placed {order.public_id} "
                    f"({order.items.count()} lines, £{order.total_pence / 100:.2f})"
                )
        except InsufficientStock as exc:
            self.stdout.write(self.style.WARNING(f"  placement raced out of stock: {exc}"))

        for advanced in advance_random_orders(rng.randint(1, 2), cancel_rate, rng):
            self.stdout.write(f"  advanced {advanced.public_id} -> {advanced.status}")
