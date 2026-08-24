"""Solution Package Platform API routes (mounted at /api/v1/packages/)."""
from django.urls import path

from . import views

app_name = "packaging"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("core/", views.CoreView.as_view(), name="core"),
    path("dependency-matrix/", views.DependencyMatrixView.as_view(), name="dependency_matrix"),
    path("preflight/", views.PreflightView.as_view(), name="preflight"),
    path("installed/", views.InstalledRegistryView.as_view(), name="installed"),
    path("installed/<uuid:installed_id>/upgrade/", views.UpgradeView.as_view(), name="upgrade"),
    path("installed/<uuid:installed_id>/rollback/",
         views.RollbackView.as_view(), name="rollback"),
    path("installed/<uuid:installed_id>/enable/", views.EnableView.as_view(), name="enable"),
    path("installed/<uuid:installed_id>/disable/", views.DisableView.as_view(), name="disable"),
]
