"""
HR lifecycle API (Phase P2.7) at /api/v1/hr/.

Thin endpoints over the native employee lifecycle. Document create/transition run as the REAL
workspace member so RBAC/ABAC/RLS apply. All configurable surface (entities/forms/views/
dashboards/reports/roles/workflows) is provisioned by the Solution Template Framework.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .blueprint import HR_OBJECTS
from .services import HRService

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


def _kw(request):
    return {"workspace_id": _ws(request), "member": _member(request), "actor_id": _uid(request)}


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        HRService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "HR numbering sequences ready."})


class DocumentCreateView(APIView):
    def post(self, request, entity_slug):
        if entity_slug not in HR_OBJECTS:
            return Response({"detail": "Unknown HR object."}, status=404)
        record = HRService.create_document(
            entity_slug=entity_slug, data=request.data or {}, **_kw(request))
        return Response(record, status=201)


class InterviewCompleteView(APIView):
    def post(self, request, record_id):
        return Response(HRService.complete_interview(record_id=record_id, **_kw(request)))


class OfferAcceptView(APIView):
    def post(self, request, record_id):
        return Response(HRService.accept_offer(record_id=record_id, **_kw(request)))


class CandidateHireView(APIView):
    def post(self, request, record_id):
        return Response(HRService.hire_candidate(record_id=record_id, **_kw(request)))


class LeaveApproveView(APIView):
    def post(self, request, record_id):
        return Response(HRService.approve_leave(record_id=record_id, **_kw(request)))


class LeaveRejectView(APIView):
    def post(self, request, record_id):
        return Response(HRService.reject_leave(record_id=record_id, **_kw(request)))


class PerformanceCompleteView(APIView):
    def post(self, request, record_id):
        return Response(HRService.complete_performance(record_id=record_id, **_kw(request)))


class EmployeePromoteView(APIView):
    def post(self, request, record_id):
        return Response(HRService.promote_employee(
            record_id=record_id, new_position=(request.data or {}).get("new_position"),
            **_kw(request)))


class EmployeeTransferView(APIView):
    def post(self, request, record_id):
        return Response(HRService.transfer_employee(
            record_id=record_id, new_department=(request.data or {}).get("new_department"),
            **_kw(request)))


class EmployeeOffboardView(APIView):
    def post(self, request, record_id):
        return Response(HRService.offboard_employee(record_id=record_id, **_kw(request)))
