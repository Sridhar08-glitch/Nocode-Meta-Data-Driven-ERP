"""Data Lineage API routes (PROJECT_HANDBOOK.md §31.3)."""
from django.urls import path

from . import views

app_name = "lineage"

urlpatterns = [
    path("nodes/", views.NodeListView.as_view(), name="node-list"),
    path("nodes/<uuid:pk>/upstream/", views.NodeUpstreamView.as_view(), name="node-upstream"),
    path("nodes/<uuid:pk>/downstream/", views.NodeDownstreamView.as_view(), name="node-downstream"),
]
