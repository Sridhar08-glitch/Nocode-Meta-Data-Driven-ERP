"""
Inventory Engine REST API (Phase P2.4) at /api/v1/inventory/.

Master data (categories, items, warehouses, locations) is owner/admin-managed. Stock transactions
(receive/issue/adjust/transfer) and reports are open to any member — warehouse staff post movements.
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Item, ItemCategory, Location, Warehouse
from .serializers import (
    ItemCategorySerializer,
    ItemSerializer,
    LocationSerializer,
    StockMovementSerializer,
    WarehouseSerializer,
)
from .services import InventoryError, InventoryService

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
        raise PermissionDenied("Inventory master-data management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


# ── Generic CRUD base for master-data models ─────────────────────────────────
class _CrudList(APIView):
    model = None
    serializer = None
    order = "id"

    def get(self, request):
        _member(request)
        qs = self.model.objects.filter(workspace_id=_ws(request))
        qs = self.filter_qs(request, qs).order_by(self.order)
        return Response(self.serializer(qs, many=True).data)

    def filter_qs(self, request, qs):
        return qs

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = self.save_new(request, ser)
        return Response(self.serializer(obj).data, status=201)

    def save_new(self, request, ser):
        return ser.save(workspace_id=_ws(request))


class _CrudDetail(APIView):
    model = None
    serializer = None

    def _get(self, request, pk):
        obj = self.model.objects.filter(workspace_id=_ws(request), id=pk).first()
        if obj is None:
            raise NotFound(f"{self.model.__name__} not found.")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(self.serializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = self._get(request, pk)
        ser = self.serializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(self.serializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        self._get(request, pk).delete()
        return Response(status=204)


# ── Categories ────────────────────────────────────────────────────────────────
class CategoryList(_CrudList):
    model, serializer, order = ItemCategory, ItemCategorySerializer, "name"


class CategoryDetail(_CrudDetail):
    model, serializer = ItemCategory, ItemCategorySerializer


# ── Items ─────────────────────────────────────────────────────────────────────
class ItemList(_CrudList):
    model, serializer, order = Item, ItemSerializer, "sku"

    def filter_qs(self, request, qs):
        if request.query_params.get("category"):
            qs = qs.filter(category_id=request.query_params["category"])
        if request.query_params.get("active") == "true":
            qs = qs.filter(is_active=True)
        return qs

    def save_new(self, request, ser):
        ws = _ws(request)
        if Item.objects.filter(workspace_id=ws, sku=ser.validated_data["sku"]).exists():
            raise ValidationError(f"Item SKU {ser.validated_data['sku']!r} already exists.")
        return ser.save(workspace_id=ws, created_by=_uid(request))


class ItemDetail(_CrudDetail):
    model, serializer = Item, ItemSerializer


# ── Warehouses ──────────────────────────────────────────────────────────────────
class WarehouseList(_CrudList):
    model, serializer, order = Warehouse, WarehouseSerializer, "code"

    def save_new(self, request, ser):
        ws = _ws(request)
        if Warehouse.objects.filter(workspace_id=ws, code=ser.validated_data["code"]).exists():
            raise ValidationError(f"Warehouse code {ser.validated_data['code']!r} already exists.")
        return ser.save(workspace_id=ws)


class WarehouseDetail(_CrudDetail):
    model, serializer = Warehouse, WarehouseSerializer


# ── Locations ───────────────────────────────────────────────────────────────────
class LocationList(_CrudList):
    model, serializer, order = Location, LocationSerializer, "code"

    def filter_qs(self, request, qs):
        if request.query_params.get("warehouse"):
            qs = qs.filter(warehouse_id=request.query_params["warehouse"])
        return qs


class LocationDetail(_CrudDetail):
    model, serializer = Location, LocationSerializer


# ── Stock transactions ───────────────────────────────────────────────────────────
def _txn_args(request):
    data = request.data if isinstance(request.data, dict) else {}
    return data


class ReceiveView(APIView):
    def post(self, request):
        _member(request)
        d = _txn_args(request)
        try:
            mv = InventoryService.receive(
                _ws(request), d.get("item"), d.get("warehouse"), d.get("quantity"),
                d.get("unit_cost", 0), location_id=d.get("location"),
                reference=d.get("reference", ""), memo=d.get("memo", ""), actor_id=_uid(request))
        except InventoryError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(StockMovementSerializer(mv).data, status=201)


class IssueView(APIView):
    def post(self, request):
        _member(request)
        d = _txn_args(request)
        try:
            mv = InventoryService.issue(
                _ws(request), d.get("item"), d.get("warehouse"), d.get("quantity"),
                location_id=d.get("location"), reference=d.get("reference", ""),
                memo=d.get("memo", ""), allow_negative=bool(d.get("allow_negative")),
                actor_id=_uid(request))
        except InventoryError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(StockMovementSerializer(mv).data, status=201)


class AdjustView(APIView):
    def post(self, request):
        _member(request)
        d = _txn_args(request)
        try:
            mv = InventoryService.adjust(
                _ws(request), d.get("item"), d.get("warehouse"), d.get("quantity_delta"),
                unit_cost=d.get("unit_cost"), reference=d.get("reference", ""),
                memo=d.get("memo", ""), actor_id=_uid(request))
        except InventoryError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(StockMovementSerializer(mv).data, status=201)


class TransferView(APIView):
    def post(self, request):
        _member(request)
        d = _txn_args(request)
        try:
            result = InventoryService.transfer(
                _ws(request), d.get("item"), d.get("from_warehouse"), d.get("to_warehouse"),
                d.get("quantity"), reference=d.get("reference", ""), memo=d.get("memo", ""),
                allow_negative=bool(d.get("allow_negative")), actor_id=_uid(request))
        except InventoryError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"out": StockMovementSerializer(result["out"]).data,
                         "in": StockMovementSerializer(result["in"]).data}, status=201)


# ── Reports ───────────────────────────────────────────────────────────────────
class StockBalanceView(APIView):
    def get(self, request):
        _member(request)
        return Response({"rows": InventoryService.stock_balance(
            _ws(request), warehouse_id=request.query_params.get("warehouse") or None,
            item_id=request.query_params.get("item") or None)})


class ValuationView(APIView):
    def get(self, request):
        _member(request)
        return Response(InventoryService.valuation(
            _ws(request), warehouse_id=request.query_params.get("warehouse") or None))


class MovementHistoryView(APIView):
    def get(self, request):
        _member(request)
        return Response({"rows": InventoryService.movement_history(
            _ws(request), item_id=request.query_params.get("item") or None,
            warehouse_id=request.query_params.get("warehouse") or None)})
