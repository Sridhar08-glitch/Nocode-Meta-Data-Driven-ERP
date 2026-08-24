"""Process-catalog routes (Phase 1.34) — mounted at /api/v1/process-catalog/."""
from django.urls import path

from . import views

app_name = "process_catalog"

urlpatterns = [
    path("", views.BlueprintListView.as_view(), name="list"),
    path("<uuid:pk>/", views.BlueprintDetailView.as_view(), name="detail"),
    path("<uuid:pk>/publish/", views.BlueprintPublishView.as_view(), name="publish"),
    path("<uuid:pk>/install/", views.BlueprintInstallView.as_view(), name="install"),
]
