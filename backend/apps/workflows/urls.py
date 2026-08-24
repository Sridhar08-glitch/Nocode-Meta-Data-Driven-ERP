"""Workflow API routes (PROJECT_HANDBOOK.md §21.7)."""
from django.urls import path

from . import views

app_name = "workflows"

urlpatterns = [
    # definitions
    path("definitions/", views.DefinitionListCreateView.as_view(), name="definition-list"),
    path("definitions/<uuid:pk>/", views.DefinitionDetailView.as_view(), name="definition-detail"),
    path("definitions/<uuid:pk>/activate/", views.DefinitionActivateView.as_view(), name="definition-activate"),
    path("definitions/<uuid:pk>/pause/", views.DefinitionPauseView.as_view(), name="definition-pause"),
    path("definitions/<uuid:pk>/duplicate/", views.DefinitionDuplicateView.as_view(), name="definition-duplicate"),
    # steps
    path("definitions/<uuid:pk>/steps/", views.StepListCreateView.as_view(), name="step-list"),
    path("definitions/<uuid:pk>/steps/<uuid:step_id>/", views.StepDetailView.as_view(), name="step-detail"),
    # edges
    path("definitions/<uuid:pk>/edges/", views.EdgeListCreateView.as_view(), name="edge-list"),
    path("definitions/<uuid:pk>/edges/<uuid:edge_id>/", views.EdgeDetailView.as_view(), name="edge-detail"),
    # webhook trigger
    path("definitions/<uuid:pk>/trigger/", views.WorkflowTriggerView.as_view(), name="definition-trigger"),
    # runs
    path("runs/", views.RunListView.as_view(), name="run-list"),
    path("runs/<uuid:run_id>/", views.RunDetailView.as_view(), name="run-detail"),
    path("runs/<uuid:run_id>/cancel/", views.RunCancelView.as_view(), name="run-cancel"),
    path("runs/<uuid:run_id>/retry/", views.RunRetryView.as_view(), name="run-retry"),
]
