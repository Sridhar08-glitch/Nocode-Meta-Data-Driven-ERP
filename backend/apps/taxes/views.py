"""
Tax Engine REST API at /api/v1/taxes/.

Tax masters (authorities / codes / rates / groups / exemptions) are admin-gated; ``calculate`` and
``summary`` are available to any workspace member (packages/UI price documents through them). The
engine is package-independent — every package consumes it via these endpoints or the
``action_calculate_tax`` / ``action_post_tax`` / ``action_reverse_tax`` workflow steps, and NONE
re-implements tax logic. Workspace-scoped (RLS applies).
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TaxAuthority, TaxCode, TaxExemption, TaxGroup
from .serializers import (
    TaxAuthoritySerializer,
    TaxCalculateSerializer,
    TaxCodeSerializer,
    TaxExemptionSerializer,
    TaxGroupSerializer,
    TaxRateSerializer,
)
from .services import TaxError, TaxService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Tax configuration requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _public_calc(calc: dict) -> dict:
    """Strip the internal ``_code`` object and stringify decimals for JSON."""
    def _s(v):
        return str(v) if v is not None else None
    return {
        "taxable_base": _s(calc.get("taxable_base")), "net": _s(calc.get("net")),
        "total_tax": _s(calc.get("total_tax")), "gross": _s(calc.get("gross")),
        "inclusive": calc.get("inclusive"), "exempt": calc.get("exempt"),
        "components": [{"code": c["code"], "type": c["type"], "rate": _s(c["rate"]),
                        "base": _s(c["base"]), "amount": _s(c["amount"]),
                        "is_compound": c["is_compound"], "exempt": c["exempt"]}
                       for c in calc.get("components", [])],
    }


class _WSModelList(APIView):
    """List/create a workspace-scoped tax master (admin writes)."""
    model = None
    serializer = None

    def get(self, request):
        qs = self.model.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:500]
        return Response(self.serializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ser.save(workspace_id=_ws(request), created_by=_uid(request))
        return Response(ser.data, status=201)


class AuthorityList(_WSModelList):
    model = TaxAuthority
    serializer = TaxAuthoritySerializer


class CodeList(_WSModelList):
    model = TaxCode
    serializer = TaxCodeSerializer


class GroupList(_WSModelList):
    model = TaxGroup
    serializer = TaxGroupSerializer


class ExemptionList(_WSModelList):
    model = TaxExemption
    serializer = TaxExemptionSerializer


class CodeDetail(APIView):
    def get(self, request, pk):
        code = TaxCode.objects.filter(workspace_id=_ws(request), id=pk).first()
        if code is None:
            raise PermissionDenied("Tax code not found.")
        return Response(TaxCodeSerializer(code).data)


class CodeRates(APIView):
    """Add a temporal rate to a tax code (admin)."""
    def post(self, request, pk):
        _require_admin(request)
        code = TaxCode.objects.filter(workspace_id=_ws(request), id=pk).first()
        if code is None:
            raise PermissionDenied("Tax code not found.")
        ser = TaxRateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ser.save(workspace_id=_ws(request), tax_code=code, created_by=_uid(request))
        return Response(ser.data, status=201)


class CalculateView(APIView):
    def post(self, request):
        ser = TaxCalculateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        try:
            calc = TaxService.calculate(_ws(request), **data)
        except TaxError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_public_calc(calc))


class SummaryView(APIView):
    def get(self, request):
        return Response(TaxService.tax_summary(
            _ws(request),
            from_date=request.query_params.get("from"),
            to_date=request.query_params.get("to")))
