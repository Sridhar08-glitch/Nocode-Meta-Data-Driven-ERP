"""
RBAC/ABAC management API (frontend F1.9) — /api/v1/permissions/.

CRUD over roles, permission grants, field permissions and data-masking rules. Owner/admin
only; workspace-scoped. The enforcement ENGINE (apps/permissions/services.py, used by
RecordService) is unchanged — this just lets the UI author the config it reads.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DataMaskingRule, FieldPermission, Permission, Role
from .serializers import (
    DataMaskingRuleSerializer,
    FieldPermissionSerializer,
    PermissionSerializer,
    RoleSerializer,
)

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    member = getattr(request, "workspace_member", None)
    if member is None or getattr(member, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Managing permissions requires an admin or owner role.")


class _WorkspaceCrud(APIView):
    """List/create + detail get/patch/delete over a workspace-scoped model. Admin-only."""

    model = None
    serializer = None

    def _qs(self, request):
        return self.model.objects.filter(workspace_id=_ws(request))

    def _obj(self, request, pk):
        obj = self._qs(request).filter(id=pk).first()
        if obj is None:
            raise NotFound(f"{self.model.__name__} not found.")
        return obj


class _ListCreate(_WorkspaceCrud):
    order_by = ("id",)

    def get(self, request):
        _require_admin(request)
        qs = self._qs(request).order_by(*self.order_by)
        # optional ?role=<id> filter where the model has a role/role_id field
        role = request.query_params.get("role")
        if role:
            field = "role_id" if hasattr(self.model, "role_id") else "role"
            qs = qs.filter(**{field: role})
        return Response(self.serializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request))
        return Response(self.serializer(obj).data, status=status.HTTP_201_CREATED)


class _Detail(_WorkspaceCrud):
    def get(self, request, pk):
        _require_admin(request)
        return Response(self.serializer(self._obj(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = self._obj(request, pk)
        ser = self.serializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(self.serializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        obj = self._obj(request, pk)
        if getattr(obj, "is_system", False):
            raise ValidationError("System objects cannot be deleted.")
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoleListCreateView(_ListCreate):
    model, serializer, order_by = Role, RoleSerializer, ("name",)


class RoleDetailView(_Detail):
    model, serializer = Role, RoleSerializer


class PermissionListCreateView(_ListCreate):
    model, serializer = Permission, PermissionSerializer


class PermissionDetailView(_Detail):
    model, serializer = Permission, PermissionSerializer


class FieldPermissionListCreateView(_ListCreate):
    model, serializer = FieldPermission, FieldPermissionSerializer


class FieldPermissionDetailView(_Detail):
    model, serializer = FieldPermission, FieldPermissionSerializer


class MaskingRuleListCreateView(_ListCreate):
    model, serializer = DataMaskingRule, DataMaskingRuleSerializer


class MaskingRuleDetailView(_Detail):
    model, serializer = DataMaskingRule, DataMaskingRuleSerializer
