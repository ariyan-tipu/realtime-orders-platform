from django.contrib import admin

from orders.models import Order, OrderItem, OrderStatusEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["variant", "quantity", "unit_price_pence"]
    can_delete = False


class OrderStatusEventInline(admin.TabularInline):
    model = OrderStatusEvent
    extra = 0
    readonly_fields = ["from_status", "to_status", "note", "created_at"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["public_id", "status", "warehouse", "total_pence", "currency", "created_at"]
    list_filter = ["status", "warehouse"]
    search_fields = ["public_id"]
    date_hierarchy = "created_at"
    readonly_fields = ["public_id", "total_pence", "created_at", "updated_at"]
    list_select_related = ["warehouse"]
    inlines = [OrderItemInline, OrderStatusEventInline]
