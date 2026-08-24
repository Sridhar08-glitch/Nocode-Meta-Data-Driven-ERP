"""
Certification API views (P2.16).

All views delegate exclusively to CertificationRunner — no direct calls to
health/simulation/report modules from this file (architecture §8 requirement).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .runner import CertificationRunner


class IntegrationRegistryView(APIView):
    """GET /api/v1/certification/integrations/ — full integration registry."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.get_integration_registry())


class ModuleHealthView(APIView):
    """GET /api/v1/certification/health/ — per-module health dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.get_module_health(request.workspace_id))


class ReadinessView(APIView):
    """GET /api/v1/certification/readiness/ — executive readiness dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.get_readiness_summary(request.workspace_id))


class CertificationReportView(APIView):
    """GET /api/v1/certification/report/ — full certification report."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.generate_certification_report(request.workspace_id))


class ArchitectureValidationView(APIView):
    """GET /api/v1/certification/architecture/ — verify single-engine architecture."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.run_architecture_validation())


class ChecklistView(APIView):
    """GET /api/v1/certification/checklist/ — 32-item certification checklist."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = CertificationRunner.get_checklist()
        return Response({"total": len(items), "checklist": items})


class SimulationListView(APIView):
    """GET /api/v1/certification/simulations/ — available scenarios."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CertificationRunner.list_scenarios())


class RunSimulationView(APIView):
    """POST /api/v1/certification/simulations/run/ — run a single scenario."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        scenario = request.data.get("scenario")
        if not scenario:
            return Response({"detail": "scenario is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = CertificationRunner.run_scenario(
                scenario, request.workspace_id, request.user.id)
        except KeyError:
            return Response({"detail": f"Unknown scenario: {scenario}"},
                            status=status.HTTP_400_BAD_REQUEST)
        http_status = status.HTTP_200_OK if result["passed"] else status.HTTP_207_MULTI_STATUS
        return Response(result, status=http_status)


class RunAllScenariosView(APIView):
    """POST /api/v1/certification/simulations/run-all/ — run all scenarios."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = CertificationRunner.run_all_scenarios(request.workspace_id, request.user.id)
        all_passed = result.get("failed", 1) == 0
        http_status = status.HTTP_200_OK if all_passed else status.HTTP_207_MULTI_STATUS
        return Response(result, status=http_status)
