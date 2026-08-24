"""
Manufacturing REST API (Phase P2.12) at /api/v1/manufacturing/.

Master data (work centers / BOMs / routings) is admin-managed. The production-order lifecycle and
the BOM/MRP/costing/OEE/traceability engines run as the workspace member; posting actions are
admin-gated. Inventory + GL postings reuse the existing engines.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers as S
from .models import (
    BillOfMaterials,
    BomComponent,
    MaterialReservation,
    ProductionOperation,
    ProductionOrder,
    Routing,
    RoutingStep,
    WorkCenter,
)
from .services import (
    BOMService,
    CostingService,
    ManufacturingError,
    MRPService,
    OEEService,
    ProductionOrderService,
    QualityService,
    TraceabilityService,
    ensure_sequences,
)

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
        raise PermissionDenied("Manufacturing management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Manufacturing numbering ready."})


# ── generic CRUD base ─────────────────────────────────────────────────────────
class _CrudList(APIView):
    model = None
    serializer = None
    filters: list = []

    def get(self, request):
        qs = self.model.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        for key in self.filters:
            val = request.query_params.get(key)
            if val:
                qs = qs.filter(**{key: val})
        return Response(self.serializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = self.model.objects.create(workspace_id=_ws(request), created_by=_uid(request),
                                        **ser.validated_data)
        return Response(self.serializer(obj).data, status=201)


class WorkCenterList(_CrudList):
    model, serializer = WorkCenter, S.WorkCenterSerializer
class ComponentList(_CrudList):
    model, serializer, filters = BomComponent, S.BomComponentSerializer, ["bom_id"]
class RoutingList(_CrudList):
    model, serializer, filters = Routing, S.RoutingSerializer, ["product_item_id"]
class RoutingStepList(_CrudList):
    model, serializer, filters = RoutingStep, S.RoutingStepSerializer, ["routing_id"]
class OrderList(_CrudList):
    model, serializer, filters = ProductionOrder, S.ProductionOrderSerializer, ["status"]
class OperationList(_CrudList):
    model, serializer, filters = ProductionOperation, S.OperationSerializer, ["production_order_id"]
class ReservationList(_CrudList):
    model, serializer, filters = MaterialReservation, S.ReservationSerializer, ["production_order_id"]


# ── BOM ───────────────────────────────────────────────────────────────────────
class BomList(APIView):
    def get(self, request):
        qs = BillOfMaterials.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        pid = request.query_params.get("product_item_id")
        if pid:
            qs = qs.filter(product_item_id=pid)
        return Response(S.BomSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        bom = BOMService.create_bom(
            workspace_id=_ws(request), product_item_id=d.get("product_item_id"),
            quantity=d.get("quantity", 1), revision=d.get("revision", "A"),
            components=d.get("components", []), actor_id=_uid(request))
        return Response(S.BomSerializer(bom).data, status=201)


class BomApprove(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            bom = BOMService.approve_bom(workspace_id=_ws(request), bom_id=pk, actor_id=_uid(request))
        except ManufacturingError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(S.BomSerializer(bom).data)


class BomExplode(APIView):
    def get(self, request):
        d = request.query_params
        reqs = BOMService.explode(
            workspace_id=_ws(request), product_item_id=d.get("product_item_id"),
            quantity=d.get("quantity", 1))
        return Response({"requirements": {k: str(v) for k, v in reqs.items()}})


# ── production order lifecycle ────────────────────────────────────────────────
class OrderCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        mo = ProductionOrderService.create_order(
            workspace_id=_ws(request), product_item_id=d.get("product_item_id"),
            quantity=d.get("quantity", 0), bom_id=d.get("bom_id"),
            routing_id=d.get("routing_id"), warehouse_id=d.get("warehouse_id"),
            source_project_id=d.get("source_project_id"), actor_id=_uid(request))
        return Response(S.ProductionOrderSerializer(mo).data, status=201)


def _order_action(request, order_id, fn, **extra):
    _require_admin(request)
    try:
        mo = fn(workspace_id=_ws(request), order_id=order_id, actor_id=_uid(request), **extra)
    except ManufacturingError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(S.ProductionOrderSerializer(mo).data)


class OrderRelease(APIView):
    def post(self, request, pk): return _order_action(request, pk, ProductionOrderService.release_order)
class OrderIssue(APIView):
    def post(self, request, pk): return _order_action(request, pk, ProductionOrderService.issue_materials)
class OrderComplete(APIView):
    def post(self, request, pk):
        d = request.data or {}
        return _order_action(request, pk, ProductionOrderService.complete_order,
                             good_qty=d.get("good_qty"), scrap_qty=d.get("scrap_qty", 0),
                             overhead_percent=d.get("overhead_percent", 10),
                             lot_number=d.get("lot_number", ""))
class OrderClose(APIView):
    def post(self, request, pk): return _order_action(request, pk, ProductionOrderService.close_order)


class OperationComplete(APIView):
    def post(self, request, pk):
        _require_admin(request)
        d = request.data or {}
        op = ProductionOrderService.complete_operation(
            workspace_id=_ws(request), operation_id=pk, labor_minutes=d.get("labor_minutes", 0),
            machine_minutes=d.get("machine_minutes", 0), downtime_minutes=d.get("downtime_minutes", 0),
            downtime_reason=d.get("downtime_reason", ""), good_qty=d.get("good_qty", 0),
            reject_qty=d.get("reject_qty", 0), actor_id=_uid(request))
        return Response(S.OperationSerializer(op).data)


# ── engines ───────────────────────────────────────────────────────────────────
class MRPRunView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        return Response(MRPService.run_mrp(
            workspace_id=_ws(request), demand=d.get("demand", []),
            run_type=d.get("run_type", "regenerative"), actor_id=_uid(request)))


class StandardCostView(APIView):
    def get(self, request):
        d = request.query_params
        return Response(CostingService.standard_cost(
            workspace_id=_ws(request), product_item_id=d.get("product_item_id"),
            quantity=d.get("quantity", 1), labor_minutes=d.get("labor_minutes", 0),
            labor_rate_per_hour=d.get("labor_rate_per_hour", 0),
            overhead_percent=d.get("overhead_percent", 10)))


class OrderOEE(APIView):
    def get(self, request, pk):
        return Response(OEEService.for_order(
            workspace_id=_ws(request), order_id=pk,
            ideal_cycle_minutes=float(request.query_params.get("ideal_cycle_minutes", 1) or 1)))


class LotTrace(APIView):
    def get(self, request, pk):
        try:
            return Response(TraceabilityService.trace(workspace_id=_ws(request), lot_id=pk))
        except ManufacturingError as exc:
            return Response({"detail": str(exc)}, status=404)


class QualityCheckCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        qc = QualityService.record_check(
            workspace_id=_ws(request), production_order_id=d.get("production_order_id"),
            name=d.get("name", "Check"), sampled_qty=d.get("sampled_qty", 0),
            passed_qty=d.get("passed_qty", 0), failed_qty=d.get("failed_qty", 0),
            sampling_percent=d.get("sampling_percent", 100), actor_id=_uid(request))
        return Response(S.QualityCheckSerializer(qc).data, status=201)


class NcrCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        ncr = QualityService.create_ncr(
            workspace_id=_ws(request), production_order_id=d.get("production_order_id"),
            defect=d.get("defect", ""), actor_id=_uid(request))
        return Response(S.NcrSerializer(ncr).data, status=201)
