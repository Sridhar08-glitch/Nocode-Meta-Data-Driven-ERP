"""
Financial KPI Library REST API at /api/v1/financial-kpis/ (F13). Member reads; admin runs setup.
Evaluation is delegated to the Analytics engine; dashboards live in the reporting platform.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import FinancialKpiCatalog, FinancialKpiError

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Financial KPI setup requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class CatalogView(APIView):
    """GET the finance KPI library (AI-readiness metadata) — optionally filtered by category."""

    def get(self, request):
        _ws(request)  # workspace-scoped access (catalog itself is global, but require a member+ws)
        category = request.query_params.get("category")
        return Response({"categories": FinancialKpiCatalog.categories(),
                         "count": len(FinancialKpiCatalog.describe()),
                         "kpis": FinancialKpiCatalog.describe(category=category)})


class CatalogItemView(APIView):
    def get(self, request, code):
        _ws(request)
        try:
            return Response(FinancialKpiCatalog.describe_one(code))
        except FinancialKpiError as exc:
            raise ValidationError(str(exc)) from exc


class DashboardTemplatesView(APIView):
    def get(self, request):
        _ws(request)
        return Response(FinancialKpiCatalog.dashboards())


class SetupView(APIView):
    """POST — seed the finance KPI definitions + dashboard templates into the workspace."""

    def post(self, request):
        _require_admin(request)
        return Response(FinancialKpiCatalog.setup(workspace_id=_ws(request),
                                                  actor_id=_uid(request)), status=201)


class EvaluateView(APIView):
    def get(self, request, code):
        try:
            return Response(FinancialKpiCatalog.evaluate(
                workspace_id=_ws(request), code=code, user_id=_uid(request)))
        except Exception as exc:  # noqa: BLE001 — analytics raises AnalyticsError on unknown code
            raise ValidationError(str(exc)) from exc


class EvaluateAllView(APIView):
    def get(self, request):
        return Response(FinancialKpiCatalog.evaluate_all(
            workspace_id=_ws(request), user_id=_uid(request)))
