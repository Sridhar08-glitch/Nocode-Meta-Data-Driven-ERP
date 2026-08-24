"""Navigation routes (Phase 1.32) — mounted at /api/v1/navigation/."""
from django.urls import path

from . import views

app_name = "studio_navigation"

urlpatterns = [
    path("", views.NavigationListCreateView.as_view(), name="list-create"),
    path("resolve/", views.NavigationResolveView.as_view(), name="resolve"),
    path("<uuid:pk>/", views.NavigationDetailView.as_view(), name="detail"),
    path("<uuid:pk>/publish/", views.NavigationPublishView.as_view(), name="publish"),
]
