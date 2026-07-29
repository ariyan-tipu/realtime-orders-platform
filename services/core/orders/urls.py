from django.urls import path
from rest_framework.routers import DefaultRouter

from orders.views import DemoOrderView, OrderViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("demo/orders/", DemoOrderView.as_view(), name="demo-orders"),
    *router.urls,
]
