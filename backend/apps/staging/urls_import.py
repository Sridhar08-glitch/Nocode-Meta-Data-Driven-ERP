"""Import API routes (PROJECT_HANDBOOK.md §29.3) — mounted at /api/v1/import/."""
from django.urls import path

from . import views

app_name = "staging_import"

urlpatterns = [
    path("jobs/", views.ImportJobListCreateView.as_view(), name="job-list"),
    path("jobs/<uuid:pk>/", views.ImportJobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/mapping/", views.ImportJobMappingView.as_view(), name="job-mapping"),
    path("jobs/<uuid:pk>/preview/", views.ImportJobPreviewView.as_view(), name="job-preview"),
    path("jobs/<uuid:pk>/rows/", views.ImportJobRowsView.as_view(), name="job-rows"),
    path("jobs/<uuid:pk>/confirm/", views.ImportJobConfirmView.as_view(), name="job-confirm"),
    path("jobs/<uuid:pk>/cancel/", views.ImportJobCancelView.as_view(), name="job-cancel"),
]
