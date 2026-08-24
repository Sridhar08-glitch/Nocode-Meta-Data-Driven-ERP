"""
Process catalog API (Phase 1.34) — /api/v1/process-catalog/.

Browse + preview = any workspace member; install into the workspace = owner/admin.
Publisher CRUD (seed/publish the global catalog) = is_staff. The catalog is global; install
targets the caller's workspace (from TenantMiddleware).
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import ProcessBlueprint
from .serializers import ProcessBlueprintSerializer

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
        raise PermissionDenied("Installing a process requires an admin or owner role.")


def _require_staff(request):
    if not getattr(request.user, "is_staff", False):
        raise PermissionDenied("Publisher actions require staff access.")


class BlueprintListView(APIView):
    def get(self, request):
        _member(request)
        blueprints = services.list_blueprints(
            category=request.query_params.get("category"),
            search=request.query_params.get("search"))
        return Response({"results": ProcessBlueprintSerializer(blueprints, many=True).data,
                         "count": len(blueprints)})

    def post(self, request):
        # Publisher: create a catalog blueprint (global).
        _require_staff(request)
        ser = ProcessBlueprintSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ProcessBlueprint.objects.filter(slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A blueprint with this slug already exists.")
        bp = ser.save()
        return Response(ProcessBlueprintSerializer(bp).data, status=status.HTTP_201_CREATED)


class BlueprintDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        try:
            bp = services.get_blueprint(pk)
        except services.ProcessCatalogError as exc:
            raise NotFound(str(exc)) from exc
        # non-staff can only see published blueprints
        if not bp.is_published and not getattr(request.user, "is_staff", False):
            raise NotFound("Blueprint not found.")
        return Response(services.preview(bp))


class BlueprintPublishView(APIView):
    def post(self, request, pk):
        _require_staff(request)
        try:
            bp = services.get_blueprint(pk)
        except services.ProcessCatalogError as exc:
            raise NotFound(str(exc)) from exc
        bp.is_published = True
        bp.save(update_fields=["is_published", "updated_at"])
        return Response(ProcessBlueprintSerializer(bp).data)


class BlueprintInstallView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            result = services.install(
                blueprint_id=pk, workspace_id=_ws(request),
                installed_by=getattr(request.user, "id", None))
        except services.ProcessCatalogError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result, status=status.HTTP_201_CREATED)
