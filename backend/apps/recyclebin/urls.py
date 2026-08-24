"""Recycle Bin API routes (PROJECT_HANDBOOK.md §31.3)."""
from django.urls import path

from . import views

app_name = "recyclebin"

urlpatterns = [
    path("", views.RecycleBinListView.as_view(), name="list"),
    path("bulk-restore/", views.RecycleBinBulkRestoreView.as_view(), name="bulk-restore"),
    path("bulk-purge/", views.RecycleBinBulkPurgeView.as_view(), name="bulk-purge"),
    path("<uuid:pk>/", views.RecycleBinDetailView.as_view(), name="detail"),
    path("<uuid:pk>/restore/", views.RecycleBinRestoreView.as_view(), name="restore"),
    path("<uuid:pk>/purge/", views.RecycleBinPurgeView.as_view(), name="purge"),
]
