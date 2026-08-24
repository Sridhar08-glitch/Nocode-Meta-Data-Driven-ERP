"""
Asset Management REST API (Phase P2.9) at /api/v1/assets/.

Asset lifecycle actions operate on the framework metadata ``asset`` record (by record-id) and
run as the real workspace member (RBAC/ABAC/RLS apply). The native depreciation + disposal
engines are admin-managed and post to the GL.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import depreciation
from . import serializers as S
from .models import DepreciationEntry, DepreciationSchedule, DisposalRecord
from .services import AssetError, AssetService, DepreciationService, DisposalService

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
        raise PermissionDenied("Asset management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _kw(request):
    return {"workspace_id": _ws(request), "member": _member(request), "actor_id": _uid(request)}


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        AssetService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Asset numbering ready."})


# ── asset lifecycle ───────────────────────────────────────────────────────────
class AssetCreate(APIView):
    def post(self, request):
        rec = AssetService.create_asset(data=request.data or {}, **_kw(request))
        return Response(rec, status=201)


class AssetAssign(APIView):
    def post(self, request, pk):
        d = request.data or {}
        asset = AssetService.assign_asset(
            asset_record_id=pk, employee=d.get("employee"),
            department=d.get("department", ""), team=d.get("team", ""), **_kw(request))
        return Response(asset)


class AssetReturn(APIView):
    def post(self, request, pk):
        return Response(AssetService.return_asset(asset_record_id=pk, **_kw(request)))


class AssetTransfer(APIView):
    def post(self, request, pk):
        d = request.data or {}
        return Response(AssetService.transfer_asset(
            asset_record_id=pk, transfer_type=d.get("transfer_type", "department"),
            from_ref=d.get("from_ref", ""), to_ref=d.get("to_ref", ""), **_kw(request)))


class AssetInspect(APIView):
    def post(self, request, pk):
        d = request.data or {}
        return Response(AssetService.record_inspection(
            asset_record_id=pk, result=d.get("result", "passed"),
            inspector=d.get("inspector"), notes=d.get("notes", ""), **_kw(request)))


class AssetRetire(APIView):
    def post(self, request, pk):
        _require_admin(request)
        d = request.data or {}
        rec = AssetService.retire_asset(
            asset_record_id=pk, reason=d.get("reason", ""),
            residual_value=d.get("residual_value", 0), **_kw(request))
        return Response(S.DisposalSerializer(rec).data, status=201)


class WorkOrderComplete(APIView):
    def post(self, request, pk):
        return Response(AssetService.complete_maintenance(work_order_id=pk, **_kw(request)))


# ── depreciation engine ───────────────────────────────────────────────────────
class ScheduleList(APIView):
    def get(self, request):
        qs = DepreciationSchedule.objects.filter(workspace_id=_ws(request))
        asset = request.query_params.get("asset_record_id")
        if asset:
            qs = qs.filter(asset_record_id=asset)
        return Response(S.ScheduleSerializer(qs.order_by("-created_at"), many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        sched = DepreciationService.create_schedule(
            workspace_id=_ws(request), asset_record_id=d.get("asset_record_id"),
            method=d.get("method", "straight_line"),
            acquisition_cost=d.get("acquisition_cost", 0),
            salvage_value=d.get("salvage_value", 0),
            useful_life_months=d.get("useful_life_months", 12),
            start_date=d.get("start_date"), actor_id=_uid(request))
        return Response(S.ScheduleSerializer(sched).data, status=201)


class ScheduleRun(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            entry = DepreciationService.run_period(
                workspace_id=_ws(request), schedule_id=pk,
                period_date=(request.data or {}).get("period_date"),
                member=_member(request), actor_id=_uid(request))
        except AssetError as exc:
            return Response({"detail": str(exc)}, status=400)
        if entry is None:
            return Response({"detail": "Fully depreciated — nothing posted."})
        return Response(S.EntrySerializer(entry).data, status=201)


class ScheduleEntries(APIView):
    def get(self, request, pk):
        qs = DepreciationEntry.objects.filter(
            workspace_id=_ws(request), schedule_id=pk).order_by("period_index")
        return Response(S.EntrySerializer(qs, many=True).data)


class DepreciationRunAll(APIView):
    def post(self, request):
        _require_admin(request)
        count = DepreciationService.run_all(
            workspace_id=_ws(request), period_date=(request.data or {}).get("period_date"),
            member=_member(request), actor_id=_uid(request))
        return Response({"posted": count})


class DepreciationPreview(APIView):
    def post(self, request):
        d = request.data or {}
        rows = depreciation.full_schedule(
            method=d.get("method", "straight_line"), cost=d.get("acquisition_cost", 0),
            salvage=d.get("salvage_value", 0),
            useful_life_months=d.get("useful_life_months", 12))
        return Response([{**r, "amount": str(r["amount"]), "accumulated": str(r["accumulated"]),
                          "net_book_value": str(r["net_book_value"])} for r in rows])


# ── disposal engine ───────────────────────────────────────────────────────────
class DisposalCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        rec = DisposalService.dispose(
            workspace_id=_ws(request), asset_record_id=d.get("asset_record_id"),
            method=d.get("method", "sale"), proceeds=d.get("proceeds", 0),
            book_value=d.get("book_value"), disposal_date=d.get("disposal_date"),
            reason=d.get("reason", ""), member=_member(request), actor_id=_uid(request))
        return Response(S.DisposalSerializer(rec).data, status=201)


class DisposalList(APIView):
    def get(self, request):
        qs = DisposalRecord.objects.filter(workspace_id=_ws(request))
        asset = request.query_params.get("asset_record_id")
        if asset:
            qs = qs.filter(asset_record_id=asset)
        return Response(S.DisposalSerializer(qs.order_by("-created_at"), many=True).data)
