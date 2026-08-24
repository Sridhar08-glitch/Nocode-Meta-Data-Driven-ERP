"""Home-layout routes (Phase 1.32) — mounted at /api/v1/home-layouts/."""
from django.urls import path

from . import views

app_name = "studio_home"

urlpatterns = [
    path("", views.HomeLayoutListCreateView.as_view(), name="list-create"),
    path("resolve/", views.HomeLayoutResolveView.as_view(), name="resolve"),
    path("<uuid:pk>/", views.HomeLayoutDetailView.as_view(), name="detail"),
    path("<uuid:pk>/publish/", views.HomeLayoutPublishView.as_view(), name="publish"),
]
