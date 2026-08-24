"""
Audit trail API (Phase 1.10). The audit log is a projection of the event store
(§5.6/§11); this surfaces it. Admin/owner only — it is compliance data.

GET /api/v1/audit/?resource_type=&resource_id=&action=&actor_id=&limit=&offset=
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog
from .serializers import AuditLogSerializer


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


class AuditListView(APIView):
    def get(self, request):
        ws = _ws(request)
        member = getattr(request, "workspace_member", None)
        if member is None or member.role not in ("owner", "admin"):
            raise PermissionDenied("Audit log access requires owner/admin.")
        qs = AuditLog.objects.filter(workspace_id=ws)
        for field in ("resource_type", "resource_id", "action"):
            value = request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        actor = request.query_params.get("actor_id")
        if actor:
            qs = qs.filter(actor_id=actor)
        qs = qs.order_by("-occurred_at")
        total = qs.count()
        try:
            limit = min(int(request.query_params.get("limit", 50)), 500)
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            limit, offset = 50, 0
        rows = AuditLogSerializer(qs[offset:offset + limit], many=True).data
        return Response({"results": rows, "count": total})
