"""Backups API routes (PROJECT_HANDBOOK.md §33.5)."""
from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    path("jobs/", views.BackupJobListView.as_view(), name="job-list"),
    path("jobs/<uuid:pk>/", views.BackupJobDetailView.as_view(), name="job-detail"),
    path("restore-jobs/", views.RestoreJobListCreateView.as_view(), name="restore-create"),
    path("restore-jobs/<uuid:pk>/", views.RestoreJobDetailView.as_view(), name="restore-detail"),
    path("restore-jobs/<uuid:pk>/confirm/",
         views.RestoreJobConfirmView.as_view(), name="restore-confirm"),
    path("retention-policies/", views.RetentionPolicyListView.as_view(), name="retention-list"),
    path("retention-policies/<uuid:pk>/",
         views.RetentionPolicyDetailView.as_view(), name="retention-detail"),
]
