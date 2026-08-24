"""
Procurement lifecycle API (Phase P2.5) at /api/v1/procurement/.

Thin endpoints over the native integrity seams. Document create/approve/post run as the
REAL workspace member so RBAC/ABAC/RLS apply (RecordService enforces them). The configurable
solution itself is installed through the Solution Template Framework, not here.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .blueprint import PROCUREMENT_OBJECTS
from .services import ProcurementError, ProcurementService

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


class SetupView(APIView):
    """Ensure the RFQ/PO/GR/VB number sequences exist for the workspace."""

    def post(self, request):
        _require_admin(request)
        ProcurementService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Procurement numbering sequences ready."})


class DocumentCreateView(APIView):
    """Create a procurement document (numbered docs get a gapless number)."""

    def post(self, request, entity_slug):
        if entity_slug not in PROCUREMENT_OBJECTS:
            return Response({"detail": "Unknown procurement object."}, status=404)
        try:
            record = ProcurementService.create_document(
                workspace_id=_ws(request), entity_slug=entity_slug,
                data=request.data or {}, member=_member(request), actor_id=_uid(request))
        except ProcurementError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(record, status=201)


class DocumentApproveView(APIView):
    def post(self, request, entity_slug, record_id):
        if entity_slug not in PROCUREMENT_OBJECTS:
            return Response({"detail": "Unknown procurement object."}, status=404)
        record = ProcurementService.approve_document(
            workspace_id=_ws(request), entity_slug=entity_slug, record_id=record_id,
            member=_member(request), actor_id=_uid(request))
        return Response(record)


class GoodsReceiptPostView(APIView):
    def post(self, request, record_id):
        record = ProcurementService.post_goods_receipt(
            workspace_id=_ws(request), record_id=record_id,
            member=_member(request), actor_id=_uid(request))
        return Response(record)


class VendorBillPostView(APIView):
    def post(self, request, record_id):
        record = ProcurementService.post_vendor_bill(
            workspace_id=_ws(request), record_id=record_id,
            member=_member(request), actor_id=_uid(request))
        return Response(record)
