"""
Approvals REST API (PROJECT_HANDBOOK.md §27.3).

Workspace-scoped approval-process CRUD + request listing/resolution. Approve/
reject enforce that the caller is an approver for the request's current level
(checked in the service); cancel is requester-or-admin.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApprovalProcess, ApprovalRequest
from .serializers import ApprovalProcessSerializer, ApprovalRequestSerializer
from .services import ApprovalError, ApprovalPermissionError, ApprovalService

_ADMIN_ROLES = {"owner", "admin"}
_WRITE_ROLES = {"owner", "admin", "member"}


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


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _resolve(fn):
    try:
        return fn()
    except ApprovalPermissionError as exc:
        raise PermissionDenied(str(exc)) from exc
    except ApprovalError as exc:
        raise ValidationError(str(exc)) from exc


# ── processes ─────────────────────────────────────────────────────────────────
class ProcessListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = ApprovalProcess.objects.filter(
            workspace_id=_ws(request), deleted_at__isnull=True).order_by("name")
        return Response({"results": ApprovalProcessSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = ApprovalProcessSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if ApprovalProcess.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A process with this slug already exists")
        obj = ser.save(workspace_id=ws)
        return Response(ApprovalProcessSerializer(obj).data, status=status.HTTP_201_CREATED)


class ProcessDetailView(APIView):
    def _get(self, request, pk):
        obj = ApprovalProcess.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Process not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(ApprovalProcessSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = ApprovalProcessSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ApprovalProcessSerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── requests ──────────────────────────────────────────────────────────────────
class RequestListView(APIView):
    def get(self, request):
        member = _member(request)
        ws = _ws(request)
        if request.query_params.get("pending_for_me") in ("1", "true", "True"):
            reqs = ApprovalService.pending_for(member.user_id, ws)
            return Response({"results": ApprovalRequestSerializer(reqs, many=True).data,
                             "count": len(reqs)})
        qs = ApprovalRequest.objects.filter(workspace_id=ws)
        for f in ("status", "record_id", "process_id"):
            if request.query_params.get(f):
                qs = qs.filter(**{f: request.query_params[f]})
        qs = qs.order_by("-created_at")[:200]
        return Response({"results": ApprovalRequestSerializer(qs, many=True).data,
                         "count": len(qs)})


class RequestDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        req = ApprovalRequest.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if req is None:
            raise NotFound("Request not found")
        return Response(ApprovalRequestSerializer(req).data)


class RequestApproveView(APIView):
    def post(self, request, pk):
        member = _member(request)
        req = _resolve(lambda: ApprovalService.approve(
            pk, member.user_id, request.data.get("comment", ""), workspace_id=_ws(request)))
        return Response(ApprovalRequestSerializer(req).data)


class RequestRejectView(APIView):
    def post(self, request, pk):
        member = _member(request)
        req = _resolve(lambda: ApprovalService.reject(
            pk, member.user_id, request.data.get("comment", ""), workspace_id=_ws(request)))
        return Response(ApprovalRequestSerializer(req).data)


class RequestCancelView(APIView):
    def post(self, request, pk):
        member = _member(request)
        is_admin = getattr(member, "role", "") in _ADMIN_ROLES
        req = _resolve(lambda: ApprovalService.cancel(
            pk, member.user_id, is_admin=is_admin, workspace_id=_ws(request)))
        return Response(ApprovalRequestSerializer(req).data)


class PendingForMeView(APIView):
    def get(self, request):
        member = _member(request)
        reqs = ApprovalService.pending_for(member.user_id, _ws(request))
        return Response({"results": ApprovalRequestSerializer(reqs, many=True).data,
                         "count": len(reqs)})
