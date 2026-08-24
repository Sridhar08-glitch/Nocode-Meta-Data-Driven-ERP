"""SLA API routes (PROJECT_HANDBOOK.md §28.4). Per-record routes live in apps.records.urls."""
from django.urls import path

from . import views

app_name = "sla"

urlpatterns = [
    path("policies/", views.PolicyListCreateView.as_view(), name="policy-list"),
    path("policies/<uuid:pk>/", views.PolicyDetailView.as_view(), name="policy-detail"),
    path("business-hours/", views.BusinessHoursListCreateView.as_view(), name="bh-list"),
    path("business-hours/<uuid:pk>/", views.BusinessHoursDetailView.as_view(), name="bh-detail"),
    path("dashboard/", views.SLADashboardView.as_view(), name="dashboard"),
]
