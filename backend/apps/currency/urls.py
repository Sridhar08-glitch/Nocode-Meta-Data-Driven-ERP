"""Multi-Currency URLs at /api/v1/currency/."""
from django.urls import path

from . import views

urlpatterns = [
    path("currencies/", views.CurrencyList.as_view(), name="currency-list"),
    path("set-base/", views.SetBaseView.as_view(), name="currency-set-base"),
    path("rates/", views.RateList.as_view(), name="currency-rates"),
    path("convert/", views.ConvertView.as_view(), name="currency-convert"),
]
