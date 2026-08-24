"""
CRM lifecycle API (Phase P2.6) at /api/v1/crm/.

Thin endpoints over the native lifecycle. Document create/transition run as the REAL workspace
member so RBAC/ABAC/RLS apply. All configurable surface (entities/forms/views/dashboards/
reports/roles/workflows) is provisioned by the Solution Template Framework, not here.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .blueprint import CRM_OBJECTS
from .services import CRMService

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


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        CRMService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "CRM numbering sequences ready."})


class DocumentCreateView(APIView):
    def post(self, request, entity_slug):
        if entity_slug not in CRM_OBJECTS:
            return Response({"detail": "Unknown CRM object."}, status=404)
        record = CRMService.create_document(
            workspace_id=_ws(request), entity_slug=entity_slug,
            data=request.data or {}, member=_member(request), actor_id=_uid(request))
        return Response(record, status=201)


class LeadQualifyView(APIView):
    def post(self, request, record_id):
        result = CRMService.qualify_lead(
            workspace_id=_ws(request), record_id=record_id,
            member=_member(request), actor_id=_uid(request))
        return Response(result)


class OpportunityWinView(APIView):
    def post(self, request, record_id):
        record = CRMService.win_opportunity(
            workspace_id=_ws(request), record_id=record_id,
            reason=(request.data or {}).get("reason", ""),
            member=_member(request), actor_id=_uid(request))
        return Response(record)


class OpportunityLoseView(APIView):
    def post(self, request, record_id):
        record = CRMService.lose_opportunity(
            workspace_id=_ws(request), record_id=record_id,
            reason=(request.data or {}).get("reason", ""),
            member=_member(request), actor_id=_uid(request))
        return Response(record)


class ActivityCompleteView(APIView):
    def post(self, request, record_id):
        record = CRMService.complete_activity(
            workspace_id=_ws(request), record_id=record_id,
            member=_member(request), actor_id=_uid(request))
        return Response(record)
