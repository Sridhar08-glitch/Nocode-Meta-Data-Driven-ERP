"""Financial KPI Library URLs at /api/v1/financial-kpis/ (F13)."""
from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.CatalogView.as_view(), name="financial-kpis-catalog"),
    path("catalog/<slug:code>/", views.CatalogItemView.as_view(), name="financial-kpis-catalog-item"),
    path("dashboards/", views.DashboardTemplatesView.as_view(), name="financial-kpis-dashboards"),
    path("setup/", views.SetupView.as_view(), name="financial-kpis-setup"),
    path("evaluate/", views.EvaluateAllView.as_view(), name="financial-kpis-evaluate-all"),
    path("evaluate/<slug:code>/", views.EvaluateView.as_view(), name="financial-kpis-evaluate"),
]
