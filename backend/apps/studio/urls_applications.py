"""Application routes (Phase 1.32) — mounted at /api/v1/applications/."""
from django.urls import path

from . import views

app_name = "studio_applications"

urlpatterns = [
    path("", views.ApplicationListCreateView.as_view(), name="list-create"),
    path("switcher/", views.ApplicationSwitcherView.as_view(), name="switcher"),
    path("<uuid:pk>/", views.ApplicationDetailView.as_view(), name="detail"),
    path("<uuid:pk>/publish/", views.ApplicationPublishView.as_view(), name="publish"),
]
