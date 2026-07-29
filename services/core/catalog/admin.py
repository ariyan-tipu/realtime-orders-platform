from django.contrib import admin

from catalog.models import Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "variants__sku"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "name", "product", "price_pence", "currency", "is_active"]
    list_filter = ["is_active", "currency"]
    search_fields = ["sku", "name", "product__name"]
