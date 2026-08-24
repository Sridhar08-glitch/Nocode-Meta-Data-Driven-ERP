"""Company platform URLs at /api/v1/companies/."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.CompanyListView.as_view(), name="company-list"),
    path("ownership/", views.OwnershipView.as_view(), name="company-ownership"),
]
