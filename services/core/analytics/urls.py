from django.urls import path

from analytics.views import TopSellersView

urlpatterns = [
    path("analytics/top-sellers/", TopSellersView.as_view(), name="top-sellers"),
]
