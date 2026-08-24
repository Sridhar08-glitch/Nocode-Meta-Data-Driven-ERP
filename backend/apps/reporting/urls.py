"""Reporting API routes (PROJECT_HANDBOOK.md §25.3)."""
from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path("", views.ReportListCreateView.as_view(), name="list-create"),
    path("validate-nql/", views.ValidateNqlView.as_view(), name="validate-nql"),
    path("<uuid:pk>/", views.ReportDetailView.as_view(), name="detail"),
    path("<uuid:pk>/run/", views.ReportRunView.as_view(), name="run"),
    path("<uuid:pk>/snapshot/", views.ReportSnapshotView.as_view(), name="snapshot"),
    path("<uuid:pk>/snapshots/", views.ReportSnapshotListView.as_view(), name="snapshot-list"),
    path("<uuid:pk>/snapshots/<uuid:snap_id>/", views.ReportSnapshotDetailView.as_view(),
         name="snapshot-detail"),
    path("<uuid:pk>/export/csv/", views.ReportExportCsvView.as_view(), name="export-csv"),
    path("<uuid:pk>/export/xlsx/", views.ReportExportXlsxView.as_view(), name="export-xlsx"),
    path("<uuid:pk>/export/pdf/", views.ReportExportPdfView.as_view(), name="export-pdf"),
]
