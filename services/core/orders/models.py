import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import ProductVariant
from inventory.models import Warehouse


class OrderStatus(models.TextChoices):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PICKING = "PICKING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# Legal lifecycle transitions. Cancellation is only possible before picking
# starts, because a picker may already be walking the floor after that.
ORDER_STATUS_FLOW: dict[str, frozenset[str]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PICKING, OrderStatus.CANCELLED}),
    OrderStatus.PICKING: frozenset({OrderStatus.PACKED}),
    OrderStatus.PACKED: frozenset({OrderStatus.SHIPPED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


class Order(models.Model):
    # Exposed in APIs and events instead of the sequential PK.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(
        max_length=12, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    total_pence = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="GBP")
    # default (not auto_now_add) so the seeder can create backdated history.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Serves the analytics window ("recent, non-cancelled orders").
            # INCLUDE must carry every column the query touches, meaning
            # warehouse_id (its GROUP BY key) and id (its join key), or the
            # planner cannot use an index-only scan and rightly falls back to
            # a seq scan; measured proof in docs/query-optimisation.md.
            models.Index(
                fields=["created_at"],
                name="order_active_created_idx",
                condition=~models.Q(status="CANCELLED"),
                include=["warehouse", "id"],
            ),
            models.Index(fields=["status"], name="order_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Order {self.public_id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    # Price snapshot at purchase time; catalogue price changes must not
    # rewrite historical orders.
    unit_price_pence = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "variant"], name="orderitem_unique_line"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orderitem_qty_gte_1"),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant.sku}"

    @property
    def line_total_pence(self) -> int:
        return self.quantity * self.unit_price_pence


class OrderStatusEvent(models.Model):
    """Append-only audit trail; one row per transition, including creation."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_events")
    # NULL is semantically distinct from any status here: it marks the
    # creation event ("there was no previous state"), so DJ001's empty-string
    # convention would erase real meaning.
    from_status = models.CharField(  # noqa: DJ001
        max_length=12, choices=OrderStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(max_length=12, choices=OrderStatus.choices)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status or '∅'} → {self.to_status}"
