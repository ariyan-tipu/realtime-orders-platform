from django.db import models

from catalog.models import ProductVariant


class Warehouse(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=120)
    # Dimensions of the picking floor grid; bin coordinates and the pick-path
    # optimiser operate in this coordinate space. The depot is (0, 0).
    grid_width = models.PositiveSmallIntegerField(default=40)
    grid_height = models.PositiveSmallIntegerField(default=15)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class Stock(models.Model):
    """On-hand quantity of one variant in one warehouse, plus its bin location.

    These rows are the unit of row-level locking during order placement: any
    transaction that changes `quantity` must first take SELECT ... FOR UPDATE
    on the row (see orders.services), which is what makes concurrent
    decrements safe. `quantity` is a PositiveIntegerField, so PostgreSQL also
    enforces quantity >= 0 as a CHECK constraint, a last line of defence if
    a future code path skips the lock.
    """

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="stock_records"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stock_records")
    quantity = models.PositiveIntegerField(default=0)
    bin_x = models.PositiveSmallIntegerField()
    bin_y = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "warehouse"], name="stock_one_row_per_variant_per_warehouse"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant.sku} @ {self.warehouse.code}: {self.quantity}"
