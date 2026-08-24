"""
Settlement REST API at /api/v1/settlement/.

Registering documents, allocating and auto-allocating are financial operations → owner/admin gated;
reads (documents, balance, aging) available to any member. Workspace-scoped. Package-independent —
packages call these or the ``action_register_settlement_document`` / ``action_allocate_payment`` /
``action_auto_allocate`` workflow steps and never re-implement matching.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SettlementDocument
from .serializers import SettlementDocumentCreateSerializer, SettlementDocumentSerializer
from .services import SettlementError, SettlementService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Settlement operations require an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class DocumentList(APIView):
    def get(self, request):
        qs = SettlementDocument.objects.filter(workspace_id=_ws(request))
        for f in ("partner_ref", "direction", "status"):
            v = request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        return Response(SettlementDocumentSerializer(
            qs.order_by("document_date", "-created_at")[:500], many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = SettlementDocumentCreateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            doc = SettlementService.register_document(
                workspace_id=_ws(request), actor_id=_uid(request), **ser.validated_data)
        except SettlementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SettlementDocumentSerializer(doc).data, status=201)


class AllocateView(APIView):
    def post(self, request):
        _require_admin(request)
        data = request.data or {}
        try:
            alloc = SettlementService.allocate(
                workspace_id=_ws(request), credit_document_id=data.get("credit_document_id"),
                debit_document_id=data.get("debit_document_id"), amount=data.get("amount"),
                external_ref=data.get("external_ref", ""), actor_id=_uid(request))
        except SettlementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"allocation_id": str(alloc.id), "amount": str(alloc.amount)}, status=201)


class AutoAllocateView(APIView):
    def post(self, request):
        _require_admin(request)
        partner = (request.data or {}).get("partner_ref")
        if not partner:
            raise ValidationError("partner_ref required.")
        return Response(SettlementService.auto_allocate(
            workspace_id=_ws(request), partner_ref=partner, actor_id=_uid(request)))


class BalanceView(APIView):
    def get(self, request):
        partner = request.query_params.get("partner_ref")
        if not partner:
            raise ValidationError("partner_ref required.")
        direction = request.query_params.get("direction", "debit")
        return Response({"partner_ref": partner, "direction": direction,
                         "outstanding": str(SettlementService.outstanding_balance(
                             _ws(request), partner, direction=direction))})


class AgingView(APIView):
    def get(self, request):
        import datetime as _dt
        raw = request.query_params.get("as_of")
        as_of = None
        if raw:
            try:
                as_of = _dt.date.fromisoformat(raw)
            except ValueError:
                as_of = None
        return Response(SettlementService.aging(
            _ws(request), direction=request.query_params.get("direction", "debit"), as_of=as_of))
