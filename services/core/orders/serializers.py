from rest_framework import serializers

from catalog.models import ProductVariant
from inventory.models import Warehouse
from orders.models import Order, OrderItem, OrderStatusEvent
from orders.services import OrderLine


class OrderItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="variant.sku", read_only=True)
    name = serializers.CharField(source="variant.name", read_only=True)
    line_total_pence = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["sku", "name", "quantity", "unit_price_pence", "line_total_pence"]


class OrderStatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusEvent
        fields = ["from_status", "to_status", "note", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    warehouse = serializers.CharField(source="warehouse.code", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "public_id",
            "status",
            "warehouse",
            "total_pence",
            "currency",
            "created_at",
            "updated_at",
            "items",
        ]


class OrderDetailSerializer(OrderSerializer):
    status_events = OrderStatusEventSerializer(many=True, read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = [*OrderSerializer.Meta.fields, "status_events"]


class OrderLineInputSerializer(serializers.Serializer):
    sku = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)


class PlaceOrderSerializer(serializers.Serializer):
    """Validates an order request and resolves SKUs into service-layer lines."""

    warehouse = serializers.SlugRelatedField(
        slug_field="code", queryset=Warehouse.objects.filter(is_active=True)
    )
    items = OrderLineInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs: dict) -> dict:
        # Merge duplicate SKUs so clients can send repeated lines safely.
        merged: dict[str, int] = {}
        for item in attrs["items"]:
            merged[item["sku"]] = merged.get(item["sku"], 0) + item["quantity"]

        variants = ProductVariant.objects.filter(sku__in=merged, is_active=True)
        by_sku = {variant.sku: variant for variant in variants}
        unknown = sorted(set(merged) - set(by_sku))
        if unknown:
            raise serializers.ValidationError({"items": f"unknown or inactive SKUs: {unknown}"})

        attrs["lines"] = [
            OrderLine(variant_id=by_sku[sku].id, quantity=quantity)
            for sku, quantity in merged.items()
        ]
        return attrs
