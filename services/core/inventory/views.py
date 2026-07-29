from rest_framework import generics

from inventory.models import Stock, Warehouse
from inventory.serializers import StockLevelSerializer, WarehouseSerializer


class WarehouseList(generics.ListAPIView):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer


class StockLevelList(generics.ListAPIView):
    serializer_class = StockLevelSerializer

    def get_queryset(self):
        queryset = Stock.objects.select_related("variant__product", "warehouse").order_by(
            "warehouse__code", "variant__sku"
        )
        warehouse = self.request.query_params.get("warehouse")
        if warehouse:
            queryset = queryset.filter(warehouse__code=warehouse)
        return queryset
