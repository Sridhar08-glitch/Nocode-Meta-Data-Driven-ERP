"""Budgets & Forecasts URLs at /api/v1/budgets/."""
from django.urls import path

from . import views

urlpatterns = [
    path("plans/", views.PlanList.as_view(), name="budget-plans"),
    path("versions/", views.VersionList.as_view(), name="budget-versions"),
    path("versions/<uuid:version_id>/lines/", views.LineView.as_view(), name="budget-lines"),
    path("versions/<uuid:version_id>/allocate/", views.AllocateView.as_view(),
         name="budget-allocate"),
    path("versions/<uuid:version_id>/submit/", views.SubmitView.as_view(), name="budget-submit"),
    path("versions/<uuid:version_id>/approve/", views.ApproveView.as_view(), name="budget-approve"),
    path("versions/<uuid:version_id>/lock/", views.LockView.as_view(), name="budget-lock"),
    path("versions/<uuid:version_id>/vs-actual/", views.BudgetVsActualView.as_view(),
         name="budget-vs-actual"),
    path("versions/<uuid:version_id>/utilization/", views.UtilizationView.as_view(),
         name="budget-utilization"),
]
