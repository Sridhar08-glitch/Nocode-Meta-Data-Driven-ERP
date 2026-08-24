"""
Analytics / KPI REST API (Phase P2.13) at /api/v1/analytics/.

KPI registry CRUD + evaluation + role scorecards + snapshots + alerts. Reports/exports/dashboards
are served by the existing ``/api/v1/reports/`` + ``/api/v1/dashboards/`` endpoints (reused, not
duplicated). Reads are member-visible; registry writes + setup are admin-gated.
"""
import uuid

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KPIDefinition
from .seeding import seed_standard_kpis
from .services import AnalyticsError, KPIService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_admin(request):
    if getattr(_member(request), "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Managing the KPI registry requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class KPISerializer(serializers.ModelSerializer):
    class Meta:
        model = KPIDefinition
        exclude = ["deleted_at", "deleted_by", "created_by", "updated_by"]
        read_only_fields = ["id", "workspace_id", "created_at", "updated_at", "is_system"]


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        n = seed_standard_kpis(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Standard KPIs ready.", "created": n})


class KPIList(APIView):
    def get(self, request):
        qs = KPIDefinition.objects.filter(workspace_id=_ws(request))
        cat = request.query_params.get("category")
        if cat:
            qs = qs.filter(category=cat)
        return Response(KPISerializer(qs.order_by("category", "name"), many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = KPISerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        kpi = KPIDefinition.objects.create(
            workspace_id=_ws(request), created_by=_uid(request), **ser.validated_data)
        return Response(KPISerializer(kpi).data, status=201)


class KPIDetail(APIView):
    def _obj(self, request, pk):
        kpi = KPIDefinition.objects.filter(workspace_id=_ws(request), id=pk).first()
        if kpi is None:
            raise PermissionDenied("Not found.")
        return kpi

    def patch(self, request, pk):
        _require_admin(request)
        kpi = self._obj(request, pk)
        ser = KPISerializer(kpi, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(updated_by=_uid(request))
        return Response(KPISerializer(kpi).data)

    def delete(self, request, pk):
        _require_admin(request)
        self._obj(request, pk).delete()
        return Response(status=204)


class KPIEvaluate(APIView):
    def get(self, request, code):
        try:
            return Response(KPIService.evaluate_code(
                workspace_id=_ws(request), code=code, user_id=_uid(request)))
        except AnalyticsError as exc:
            return Response({"detail": str(exc)}, status=404)


class KPIEvaluateAll(APIView):
    def get(self, request):
        return Response(KPIService.evaluate_all(
            workspace_id=_ws(request), category=request.query_params.get("category"),
            user_id=_uid(request)))


class Scorecard(APIView):
    def get(self, request, role):
        return Response(KPIService.scorecard(
            workspace_id=_ws(request), role=role, user_id=_uid(request)))


class SnapshotView(APIView):
    def post(self, request):
        _require_admin(request)
        n = KPIService.snapshot(workspace_id=_ws(request),
                                period=(request.data or {}).get("period", ""), user_id=_uid(request))
        return Response({"snapshotted": n})


class AlertsCheck(APIView):
    def post(self, request):
        _require_admin(request)
        return Response({"alerts": KPIService.check_alerts(
            workspace_id=_ws(request), user_id=_uid(request))})


class TrendView(APIView):
    def get(self, request, code):
        return Response(KPIService.trend(
            workspace_id=_ws(request), code=code,
            limit=int(request.query_params.get("limit", 12) or 12)))
