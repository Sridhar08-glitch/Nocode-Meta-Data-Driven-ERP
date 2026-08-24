"""
Dependency / Impact Analysis API (Phase P2.14) at /api/v1/dependency/.

A read-only change-safety surface. Discovery is delegated to ``apps.metadata.impact`` (the system
of record); this API only orchestrates (analyze / graph / safe-delete / change-preview / promotion
precheck / executive summary). Workspace-scoped; analysis is member-visible, promotion checks +
executive summary are admin-gated.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.metadata.impact import OBJECT_TYPES

from .services import AnalysisService

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
        raise PermissionDenied("This action requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _params(request):
    ot = request.query_params.get("object_type") or (request.data or {}).get("object_type")
    oid = request.query_params.get("object_id") or (request.data or {}).get("object_id")
    if ot not in OBJECT_TYPES or not oid:
        raise PermissionDenied("object_type (one of the known types) and object_id are required.")
    return ot, oid


class ObjectTypesView(APIView):
    def get(self, request):
        _member(request)
        return Response({"object_types": OBJECT_TYPES})


class AnalyzeView(APIView):
    def get(self, request):
        _member(request)
        ot, oid = _params(request)
        return Response(AnalysisService.analyze(
            workspace_id=_ws(request), object_type=ot, object_id=oid, actor_id=_uid(request)))


class GraphView(APIView):
    def get(self, request):
        _member(request)
        ot, oid = _params(request)
        depth = int(request.query_params.get("depth", 2) or 2)
        return Response(AnalysisService.graph(
            workspace_id=_ws(request), object_type=ot, object_id=oid, depth=depth))


class SafeDeleteView(APIView):
    def get(self, request):
        _member(request)
        ot, oid = _params(request)
        return Response(AnalysisService.safe_delete(
            workspace_id=_ws(request), object_type=ot, object_id=oid, actor_id=_uid(request)))


class ChangePreviewView(APIView):
    def post(self, request):
        _member(request)
        ot, oid = _params(request)
        return Response(AnalysisService.change_preview(
            workspace_id=_ws(request), object_type=ot, object_id=oid,
            change=(request.data or {}).get("change", "rename"), actor_id=_uid(request)))


class PromotionPrecheckView(APIView):
    def post(self, request):
        _require_admin(request)
        return Response(AnalysisService.promotion_precheck(
            workspace_id=_ws(request), objects=(request.data or {}).get("objects", []),
            actor_id=_uid(request)))


class ExecutiveSummaryView(APIView):
    def get(self, request):
        _require_admin(request)
        return Response(AnalysisService.executive_summary(workspace_id=_ws(request)))
