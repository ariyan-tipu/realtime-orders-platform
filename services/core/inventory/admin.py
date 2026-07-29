from django.contrib import admin

from inventory.models import Stock, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "grid_width", "grid_height", "is_active"]


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ["variant", "warehouse", "quantity", "bin_x", "bin_y", "updated_at"]
    list_filter = ["warehouse"]
    search_fields = ["variant__sku", "variant__product__name"]
    list_select_related = ["variant__product", "warehouse"]
