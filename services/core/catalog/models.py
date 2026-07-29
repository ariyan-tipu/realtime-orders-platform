from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductVariant(models.Model):
    """A sellable unit (SKU). Prices are integer pence; never floats near money."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    price_pence = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="GBP")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_pence__gt=0), name="variant_price_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sku} ({self.name})"
