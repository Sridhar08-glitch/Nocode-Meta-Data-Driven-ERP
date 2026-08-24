"""Export API routes (PROJECT_HANDBOOK.md §29.3) — mounted at /api/v1/export/."""
from django.urls import path

from . import views

app_name = "staging_export"

urlpatterns = [
    path("jobs/", views.ExportJobListCreateView.as_view(), name="job-list"),
    path("jobs/<uuid:pk>/", views.ExportJobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/download/", views.ExportJobDownloadView.as_view(), name="job-download"),
]
