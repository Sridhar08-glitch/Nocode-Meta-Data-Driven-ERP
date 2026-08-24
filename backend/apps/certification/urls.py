from django.urls import path

from .views import (
    ArchitectureValidationView,
    CertificationReportView,
    ChecklistView,
    IntegrationRegistryView,
    ModuleHealthView,
    ReadinessView,
    RunAllScenariosView,
    RunSimulationView,
    SimulationListView,
)

urlpatterns = [
    path("integrations/", IntegrationRegistryView.as_view()),
    path("health/", ModuleHealthView.as_view()),
    path("readiness/", ReadinessView.as_view()),
    path("report/", CertificationReportView.as_view()),
    path("architecture/", ArchitectureValidationView.as_view()),
    path("checklist/", ChecklistView.as_view()),
    path("simulations/", SimulationListView.as_view()),
    path("simulations/run/", RunSimulationView.as_view()),
    path("simulations/run-all/", RunAllScenariosView.as_view()),
]
