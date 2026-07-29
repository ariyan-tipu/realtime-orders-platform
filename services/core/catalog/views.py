from rest_framework import viewsets

from catalog.models import Product
from catalog.serializers import ProductSerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).prefetch_related("variants").order_by("name")
    serializer_class = ProductSerializer
