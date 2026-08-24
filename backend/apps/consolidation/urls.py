"""Consolidation URLs at /api/v1/consolidation/."""
from django.urls import path

from . import views

urlpatterns = [
    path("intercompany/", views.IntercompanyView.as_view(), name="consolidation-intercompany"),
    path("runs/", views.RunView.as_view(), name="consolidation-runs"),
    path("runs/<uuid:pk>/", views.RunDetail.as_view(), name="consolidation-run"),
    path("runs/<uuid:pk>/worksheet/", views.RunWorksheetView.as_view(), name="consolidation-ws"),
]
