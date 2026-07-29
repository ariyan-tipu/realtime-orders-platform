from django.urls import path

from inventory.views import StockLevelList, WarehouseList

urlpatterns = [
    path("warehouses/", WarehouseList.as_view(), name="warehouse-list"),
    path("stock/", StockLevelList.as_view(), name="stock-list"),
]
