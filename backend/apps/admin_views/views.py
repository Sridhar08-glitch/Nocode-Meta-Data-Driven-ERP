"""Admin operational views (Phase 1.31) — /api/v1/admin/."""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import compute_health

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    member = getattr(request, "workspace_member", None)
    if member is None or getattr(member, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Tenant health requires an admin or owner role.")


class TenantHealthView(APIView):
    def get(self, request):
        _require_admin(request)
        return Response(compute_health(_ws(request)))
