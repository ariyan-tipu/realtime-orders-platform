"""Minimal hand-rolled builders: enough structure for tests without a
factory framework dependency."""

from django.contrib.auth.models import User

from catalog.models import Product, ProductVariant
from inventory.models import Stock, Warehouse


def make_user(username: str = "alice") -> User:
    return User.objects.create_user(username=username, password="test-password")


def make_warehouse(code: str = "LDN", **kwargs: object) -> Warehouse:
    return Warehouse.objects.create(code=code, name=f"{code} Fulfilment Centre", **kwargs)


def make_variant(
    sku: str = "SKU-1",
    price_pence: int = 1000,
    *,
    product: Product | None = None,
    **kwargs: object,
) -> ProductVariant:
    product = product or Product.objects.create(
        name=f"Product {sku}", slug=f"product-{sku.lower()}"
    )
    return ProductVariant.objects.create(
        product=product, sku=sku, name="One Size", price_pence=price_pence, **kwargs
    )


def make_stock(
    variant: ProductVariant,
    warehouse: Warehouse,
    quantity: int = 10,
    bin_x: int = 3,
    bin_y: int = 4,
) -> Stock:
    return Stock.objects.create(
        variant=variant, warehouse=warehouse, quantity=quantity, bin_x=bin_x, bin_y=bin_y
    )
