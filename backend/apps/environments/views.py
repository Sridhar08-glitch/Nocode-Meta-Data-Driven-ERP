"""
Environment Promotion REST API (Phase P2.15) at /api/v1/environments/.

Orchestration over Config VCS + P2.14 precheck. Reads are member-visible; promotion lifecycle
(create/approve/execute/rollback) is admin-gated and enforces segregation of duties in the service.
"""
import uuid

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Environment, PromotionApproval, PromotionPackage
from .services import PromotionError, PromotionService

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
        raise PermissionDenied("Environment promotion requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class EnvSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        exclude = ["deleted_at", "deleted_by", "created_by", "updated_by"]


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionPackage
        exclude = ["deleted_at", "deleted_by", "updated_by"]


class ApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionApproval
        exclude = ["deleted_at", "deleted_by", "updated_by"]


class EnvironmentsView(APIView):
    def get(self, request):
        _member(request)
        envs = Environment.objects.filter(workspace_id=_ws(request)).order_by("sequence")
        return Response(EnvSerializer(envs, many=True).data)

    def post(self, request):  # setup
        _require_admin(request)
        envs = PromotionService.ensure_environments(
            workspace_id=_ws(request), actor_id=_uid(request))
        return Response(EnvSerializer(envs, many=True).data, status=201)


class PackageList(APIView):
    def get(self, request):
        qs = PromotionPackage.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return Response(PackageSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        try:
            pkg = PromotionService.create_package(
                workspace_id=_ws(request), source_env_id=d.get("source_env_id"),
                target_env_id=d.get("target_env_id"), name=d.get("name", "Promotion"),
                objects=d.get("objects", []), actor_id=_uid(request))
        except PromotionError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PackageSerializer(pkg).data, status=201)


class PackageDetail(APIView):
    def get(self, request, pk):
        pkg = PromotionPackage.objects.filter(workspace_id=_ws(request), id=pk).first()
        if pkg is None:
            return Response({"detail": "Not found."}, status=404)
        data = PackageSerializer(pkg).data
        data["approvals"] = ApprovalSerializer(PromotionApproval.objects.filter(
            workspace_id=_ws(request), package_id=pk), many=True).data
        return Response(data)


def _pkg_action(request, pk, fn, **extra):
    _require_admin(request)
    try:
        out = fn(workspace_id=_ws(request), package_id=pk, actor_id=_uid(request), **extra)
    except PromotionError as exc:
        return Response({"detail": str(exc)}, status=400)
    return out


class PackageApprove(APIView):
    def post(self, request, pk):
        out = _pkg_action(request, pk, PromotionService.approve,
                          role=(request.data or {}).get("role", "approver"))
        return out if isinstance(out, Response) else Response(PackageSerializer(out).data)


class PackageExecute(APIView):
    def post(self, request, pk):
        out = _pkg_action(request, pk, PromotionService.execute,
                          dry_run=bool((request.data or {}).get("dry_run", False)))
        return out if isinstance(out, Response) else Response(out)


class PackageRollback(APIView):
    def post(self, request, pk):
        out = _pkg_action(request, pk, PromotionService.rollback)
        return out if isinstance(out, Response) else Response(PackageSerializer(out).data)


class PromotionDashboard(APIView):
    def get(self, request):
        _require_admin(request)
        return Response(PromotionService.dashboard(workspace_id=_ws(request)))
