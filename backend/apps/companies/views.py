"""Company platform REST API at /api/v1/companies/. Admin-gated writes; member reads."""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company
from .services import CompanyError, CompanyService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Company maintenance requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class CompanyListView(APIView):
    def get(self, request):
        qs = Company.objects.filter(workspace_id=_ws(request)).order_by("code")
        return Response([{"id": str(c.id), "code": c.code, "name": c.name,
                          "functional_currency": c.functional_currency,
                          "parent": str(c.parent_id) if c.parent_id else None,
                          "is_group": c.is_group, "is_default": c.is_default,
                          "is_active": c.is_active} for c in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        if not d.get("code"):
            raise ValidationError("code required.")
        c = CompanyService.ensure_company(
            workspace_id=_ws(request), code=d["code"], name=d.get("name", ""),
            functional_currency=d.get("functional_currency", ""),
            parent_code=d.get("parent_code", ""), is_group=bool(d.get("is_group", False)),
            is_elimination=bool(d.get("is_elimination", False)), actor_id=_uid(request))
        return Response({"id": str(c.id), "code": c.code}, status=201)


class OwnershipView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        try:
            o = CompanyService.set_ownership(
                workspace_id=_ws(request), parent_code=d.get("parent_code"),
                subsidiary_code=d.get("subsidiary_code"), ownership_pct=d.get("ownership_pct", 100),
                effective_from=d.get("effective_from"), effective_to=d.get("effective_to"),
                actor_id=_uid(request))
        except CompanyError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"id": str(o.id), "ownership_pct": str(o.ownership_pct)}, status=201)
