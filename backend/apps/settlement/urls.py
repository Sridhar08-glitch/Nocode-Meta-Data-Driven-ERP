"""Settlement URLs at /api/v1/settlement/."""
from django.urls import path

from . import views

urlpatterns = [
    path("documents/", views.DocumentList.as_view(), name="settlement-documents"),
    path("allocate/", views.AllocateView.as_view(), name="settlement-allocate"),
    path("auto-allocate/", views.AutoAllocateView.as_view(), name="settlement-auto-allocate"),
    path("balance/", views.BalanceView.as_view(), name="settlement-balance"),
    path("aging/", views.AgingView.as_view(), name="settlement-aging"),
]
