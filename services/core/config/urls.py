from django.contrib import admin
from django.urls import include, path

from config.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/", include("catalog.urls")),
    path("api/", include("inventory.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("analytics.urls")),
]
