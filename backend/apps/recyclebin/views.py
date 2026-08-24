"""
Recycle Bin REST API (PROJECT_HANDBOOK.md §31.3) at /api/v1/recyclebin/.

Workspace-scoped. Restore is role-gated (owner/admin/member); permanent purge
requires admin/owner. Entries from other workspaces are never visible.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RecycleBinEntry
from .serializers import RecycleBinEntrySerializer
from .services import RecycleBinError, RecycleBinService

_WRITE_ROLES = {"owner", "admin", "member"}
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


def _require(request, roles):
    m = _member(request)
    if getattr(m, "role", "") not in roles:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _entry(request, pk) -> RecycleBinEntry:
    e = RecycleBinEntry.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if e is None:
        raise NotFound("Recycle bin entry not found")
    return e


class RecycleBinListView(APIView):
    def get(self, request):
        _member(request)
        qs = RecycleBinService.list_entries(
            _ws(request),
            include_purged=request.query_params.get("include_purged") in ("1", "true"))
        if request.query_params.get("entity_slug"):
            qs = qs.filter(entity_slug=request.query_params["entity_slug"])
        qs = qs[:300]
        return Response({"results": RecycleBinEntrySerializer(qs, many=True).data,
                         "count": len(qs)})


class RecycleBinDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(RecycleBinEntrySerializer(_entry(request, pk)).data)


class RecycleBinRestoreView(APIView):
    def post(self, request, pk):
        member = _require(request, _WRITE_ROLES)
        entry = _entry(request, pk)
        try:
            RecycleBinService.restore(entry.id, member.user_id)
        except RecycleBinError as exc:
            raise NotFound(str(exc)) from exc
        return Response({"restored": True, "record_id": str(entry.record_id)})


class RecycleBinPurgeView(APIView):
    def post(self, request, pk):
        member = _require(request, _ADMIN_ROLES)
        entry = _entry(request, pk)
        RecycleBinService.purge_entry(entry.id, member.user_id)
        return Response({"purged": True})


class RecycleBinBulkRestoreView(APIView):
    def post(self, request):
        member = _require(request, _WRITE_ROLES)
        ws = _ws(request)
        ids = request.data.get("entry_ids", [])
        restored = 0
        for eid in ids:
            entry = RecycleBinEntry.objects.filter(id=eid, workspace_id=ws).first()
            if entry is None:
                continue
            try:
                RecycleBinService.restore(entry.id, member.user_id)
                restored += 1
            except RecycleBinError:
                continue
        return Response({"restored": restored})


class RecycleBinBulkPurgeView(APIView):
    def post(self, request):
        member = _require(request, _ADMIN_ROLES)
        ws = _ws(request)
        ids = request.data.get("entry_ids", [])
        purged = 0
        for eid in ids:
            entry = RecycleBinEntry.objects.filter(id=eid, workspace_id=ws).first()
            if entry is None:
                continue
            RecycleBinService.purge_entry(entry.id, member.user_id)
            purged += 1
        return Response({"purged": purged}, status=status.HTTP_200_OK)
