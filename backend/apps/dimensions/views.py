"""
Financial Dimensions REST API at /api/v1/dimensions/.

Dimension + value maintenance is admin-gated (CRUD only — no workflows); reads + validation available
to any member. Workspace-scoped. Package-independent — every package tags journal lines with these.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FinancialDimension, FinancialDimensionValue
from .services import DimensionError, DimensionService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Dimension maintenance requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class DimensionList(APIView):
    def get(self, request):
        qs = FinancialDimension.objects.filter(workspace_id=_ws(request)).order_by("sequence", "code")
        return Response([{"id": str(d.id), "code": d.code, "name": d.name,
                          "dimension_type": d.dimension_type, "is_required": d.is_required,
                          "is_hierarchical": d.is_hierarchical, "allow_posting": d.allow_posting,
                          "is_active": d.is_active} for d in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        if not d.get("code"):
            raise ValidationError("code required.")
        dim = DimensionService.ensure_dimension(
            workspace_id=_ws(request), code=d["code"], name=d.get("name", ""),
            dimension_type=d.get("dimension_type", "other"),
            is_required=bool(d.get("is_required", False)),
            is_hierarchical=bool(d.get("is_hierarchical", False)),
            allow_posting=bool(d.get("allow_posting", True)),
            sequence=int(d.get("sequence", 0)), actor_id=_uid(request))
        return Response({"id": str(dim.id), "code": dim.code}, status=201)


class ValueList(APIView):
    def get(self, request):
        qs = FinancialDimensionValue.objects.filter(workspace_id=_ws(request))
        dcode = request.query_params.get("dimension")
        if dcode:
            qs = qs.filter(dimension__code=dcode)
        return Response([{"id": str(v.id), "dimension": v.dimension.code, "code": v.code,
                          "name": v.name, "parent": v.parent.code if v.parent_id else None,
                          "is_active": v.is_active} for v in qs.select_related("dimension", "parent")])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        for f in ("dimension", "code"):
            if not d.get(f):
                raise ValidationError(f"{f} required.")
        try:
            val = DimensionService.add_value(
                workspace_id=_ws(request), dimension_code=d["dimension"], code=d["code"],
                name=d.get("name", ""), parent_code=d.get("parent", ""),
                effective_from=d.get("effective_from"), effective_to=d.get("effective_to"),
                actor_id=_uid(request))
        except DimensionError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"id": str(val.id), "code": val.code}, status=201)


class ValidateView(APIView):
    def post(self, request):
        d = request.data or {}
        errors = DimensionService.validate_map(
            _ws(request), d.get("dimensions", {}) or {}, on_date=d.get("on_date"),
            enforce_required=bool(d.get("enforce_required", False)))
        return Response({"valid": not errors, "errors": errors})
