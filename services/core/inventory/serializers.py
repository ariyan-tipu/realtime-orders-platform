from rest_framework import serializers

from inventory.models import Stock, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["code", "name", "grid_width", "grid_height", "is_active"]


class StockLevelSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="variant.sku", read_only=True)
    product = serializers.CharField(source="variant.product.name", read_only=True)
    warehouse = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = Stock
        fields = ["sku", "product", "warehouse", "quantity", "bin_x", "bin_y", "updated_at"]
