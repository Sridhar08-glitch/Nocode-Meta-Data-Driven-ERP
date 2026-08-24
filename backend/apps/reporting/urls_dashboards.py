"""Dashboard API routes (Phase 1.31) — mounted at /api/v1/dashboards/."""
from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("", views.DashboardListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.DashboardDetailView.as_view(), name="detail"),
    path("<uuid:pk>/run/", views.DashboardRunView.as_view(), name="run"),
    path("<uuid:pk>/export/pdf/", views.DashboardExportPdfView.as_view(), name="export-pdf"),
    path("<uuid:pk>/widgets/", views.DashboardWidgetListCreateView.as_view(), name="widget-list"),
    path("<uuid:pk>/widgets/<uuid:wid>/", views.DashboardWidgetDetailView.as_view(),
         name="widget-detail"),
]
