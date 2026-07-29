"""Seed a realistic demo dataset: catalogue, warehouses, stock and a month of
backdated order history.

History is bulk-inserted rather than routed through the service layer; these
are *past* orders whose stock movements have already washed through, so
replaying them against current stock would be both slow and wrong. Live
traffic (demo_orders, the API) always uses the real service layer.
"""

import os
import random
from datetime import timedelta
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from catalog.models import Product, ProductVariant
from inventory.models import Stock, Warehouse
from orders.models import Order, OrderItem, OrderStatus, OrderStatusEvent

WAREHOUSES = [
    ("LDN", "London Fulfilment Centre"),
    ("MCR", "Manchester Fulfilment Centre"),
    ("BHM", "Birmingham Fulfilment Centre"),
]

PRODUCT_NOUNS = [
    "Backpack",
    "Mug",
    "Hoodie",
    "Notebook",
    "Desk Lamp",
    "Water Bottle",
    "Keyboard",
    "Mouse Mat",
    "Beanie",
    "T-Shirt",
    "Socks",
    "Umbrella",
    "Phone Stand",
    "Tote Bag",
    "Cap",
    "Scarf",
    "Poster",
    "Sticker Pack",
    "Pen Set",
    "Travel Adapter",
    "Power Bank",
    "Headphone Stand",
    "Coaster Set",
    "Laptop Sleeve",
    "Gym Towel",
    "Running Belt",
    "Yoga Mat",
    "Puzzle",
    "Candle",
    "Plant Pot",
]

VARIANT_NAMES = ["Small", "Medium", "Large", "One Size", "Limited Edition"]

STATUS_LADDER = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.PICKING,
    OrderStatus.PACKED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
]

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = "Seed demo catalogue, stock and backdated order history"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--products", type=int, default=120)
        parser.add_argument("--users", type=int, default=40)
        parser.add_argument("--orders", type=int, default=6000)
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument(
            "--recency-skew",
            type=float,
            default=1.6,
            help="Exponent skewing order history towards recent days (1.0 = uniform)",
        )
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--flush", action="store_true", help="Delete previously seeded data first"
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if Product.objects.exists():
            if not options["flush"]:
                raise CommandError("Database already seeded. Pass --flush to reseed from scratch.")
            self._flush()

        rng = random.Random(options["seed"])
        Faker.seed(options["seed"])
        fake = Faker("en_GB")

        self._ensure_superuser()
        users = self._create_users(options["users"])
        warehouses = self._create_warehouses()
        variants = self._create_catalog(rng, fake, options["products"])
        stocks = self._create_stock(rng, warehouses, variants)
        order_count = self._create_order_history(
            rng,
            users,
            warehouses,
            stocks,
            options["orders"],
            options["days"],
            options["recency_skew"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(variants)} variants across {len(warehouses)} warehouses, "
                f"{len(stocks)} stock rows, {order_count} orders."
            )
        )

    def _flush(self) -> None:
        self.stdout.write("Flushing previously seeded data...")
        Order.objects.all().delete()  # cascades to items and status events
        Stock.objects.all().delete()
        ProductVariant.objects.all().delete()
        Product.objects.all().delete()
        Warehouse.objects.all().delete()
        User.objects.filter(is_staff=False, is_superuser=False).delete()

    def _ensure_superuser(self) -> None:
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin-dev-only")
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, password=password, email="")
            self.stdout.write(f"Created superuser '{username}' (password from env).")

    def _create_users(self, count: int) -> list[User]:
        users = [
            User(username=f"customer-{index:03d}", password="!")  # unusable password
            for index in range(1, count + 1)
        ]
        return User.objects.bulk_create(users)

    def _create_warehouses(self) -> list[Warehouse]:
        return Warehouse.objects.bulk_create(
            Warehouse(code=code, name=name, grid_width=40, grid_height=15)
            for code, name in WAREHOUSES
        )

    def _create_catalog(
        self, rng: random.Random, fake: Faker, product_count: int
    ) -> list[ProductVariant]:
        products: list[Product] = []
        used_names: set[str] = set()
        while len(products) < product_count:
            name = f"{fake.color_name()} {rng.choice(PRODUCT_NOUNS)}"
            if name in used_names:
                continue
            used_names.add(name)
            products.append(
                Product(name=name, slug=slugify(name), description=fake.sentence(nb_words=12))
            )
        Product.objects.bulk_create(products)

        variants: list[ProductVariant] = []
        for product_index, product in enumerate(products):
            for variant_index in range(rng.randint(1, 3)):
                variants.append(
                    ProductVariant(
                        product=product,
                        sku=f"P{product_index:04d}-{variant_index}",
                        name=VARIANT_NAMES[variant_index],
                        price_pence=rng.randrange(500, 15000, 25),
                    )
                )
        return ProductVariant.objects.bulk_create(variants)

    def _create_stock(
        self, rng: random.Random, warehouses: list[Warehouse], variants: list[ProductVariant]
    ) -> list[Stock]:
        stocks = [
            Stock(
                variant=variant,
                warehouse=warehouse,
                quantity=rng.randint(40, 400),
                bin_x=rng.randint(1, warehouse.grid_width - 1),
                bin_y=rng.randint(1, warehouse.grid_height - 1),
            )
            for warehouse in warehouses
            for variant in variants
            if rng.random() < 0.85  # not every SKU is stocked everywhere
        ]
        return Stock.objects.bulk_create(stocks, batch_size=BATCH_SIZE)

    def _create_order_history(
        self,
        rng: random.Random,
        users: list[User],
        warehouses: list[Warehouse],
        stocks: list[Stock],
        order_count: int,
        days: int,
        recency_skew: float,
    ) -> int:
        pool_by_warehouse: dict[int, list[ProductVariant]] = {}
        for stock in stocks:
            pool_by_warehouse.setdefault(stock.warehouse_id, []).append(stock.variant)

        now = timezone.now()
        created = 0
        while created < order_count:
            batch = min(BATCH_SIZE, order_count - created)
            orders: list[Order] = []
            lines: list[list[tuple[ProductVariant, int]]] = []
            for _ in range(batch):
                warehouse = rng.choice(warehouses)
                # The exponent skews history towards recent days (default 1.6)
                # so the 24h analytics window has plenty of data; 1.0 gives a
                # uniform spread for low-selectivity benchmarking.
                age_seconds = (rng.random() ** recency_skew) * days * 86400
                created_at = now - timedelta(seconds=age_seconds)
                variants = rng.sample(
                    pool_by_warehouse[warehouse.id],
                    k=min(rng.randint(1, 4), len(pool_by_warehouse[warehouse.id])),
                )
                order_lines = [(variant, rng.randint(1, 3)) for variant in variants]
                total = sum(qty * variant.price_pence for variant, qty in order_lines)
                orders.append(
                    Order(
                        user=rng.choice(users),
                        warehouse=warehouse,
                        status=self._status_for_age(rng, now - created_at),
                        total_pence=total,
                        created_at=created_at,
                    )
                )
                lines.append(order_lines)

            Order.objects.bulk_create(orders, batch_size=BATCH_SIZE)
            items = [
                OrderItem(
                    order=order,
                    variant=variant,
                    quantity=qty,
                    unit_price_pence=variant.price_pence,
                )
                for order, order_lines in zip(orders, lines, strict=True)
                for variant, qty in order_lines
            ]
            OrderItem.objects.bulk_create(items, batch_size=BATCH_SIZE)
            events = [event for order in orders for event in self._events_for(rng, order)]
            OrderStatusEvent.objects.bulk_create(events, batch_size=BATCH_SIZE)

            created += batch
            self.stdout.write(f"  orders: {created}/{order_count}")
        return created

    @staticmethod
    def _status_for_age(rng: random.Random, age: timedelta) -> str:
        hours = age.total_seconds() / 3600
        if hours < 1:
            choices = [OrderStatus.PENDING] * 3 + [OrderStatus.CONFIRMED] * 2
        elif hours < 6:
            choices = [
                OrderStatus.CONFIRMED,
                OrderStatus.PICKING,
                OrderStatus.PACKED,
                OrderStatus.SHIPPED,
            ]
        elif hours < 48:
            choices = [OrderStatus.SHIPPED] * 2 + [OrderStatus.DELIVERED] * 3
        else:
            choices = (
                [OrderStatus.DELIVERED] * 87
                + [OrderStatus.CANCELLED] * 8
                + [OrderStatus.SHIPPED] * 5
            )
        return rng.choice(choices)

    @staticmethod
    def _events_for(rng: random.Random, order: Order) -> list[OrderStatusEvent]:
        if order.status == OrderStatus.CANCELLED:
            path = [OrderStatus.PENDING, OrderStatus.CANCELLED]
        else:
            path = STATUS_LADDER[: STATUS_LADDER.index(OrderStatus(order.status)) + 1]

        events = []
        previous: str | None = None
        occurred = order.created_at
        for step in path:
            events.append(
                OrderStatusEvent(
                    order=order, from_status=previous, to_status=step, created_at=occurred
                )
            )
            previous = step
            occurred += timedelta(minutes=rng.randint(10, 240))
        return events
