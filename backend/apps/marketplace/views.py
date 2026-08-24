"""
Marketplace REST API (PROJECT_HANDBOOK.md §34.4) at /api/v1/marketplace/.

Three realms:
  * Public browse (read-only, unauthenticated) of published plugins + versions.
  * Workspace plugin management (authenticated member) — install/uninstall/upgrade/rollback.
  * Publisher management (``is_staff`` only) — plugin CRUD + publish/deprecate + versions.
"""
import hashlib
import json
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InstalledPlugin, MarketplacePlugin, PluginVersion
from .serializers import (
    InstalledPluginSerializer,
    MarketplacePluginSerializer,
    PluginVersionListSerializer,
    PluginVersionSerializer,
)
from .services import MarketplaceError, MarketplaceService
from .validators import validate_manifest


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


def _require_staff(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False) or not getattr(
            user, "is_staff", False):
        raise PermissionDenied("Publisher (staff) access required.")
    return user


# ── public browse ────────────────────────────────────────────────────────────
class PluginBrowseView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        plugins = MarketplaceService.list_plugins(
            category=request.query_params.get("category"),
            search=request.query_params.get("search"),
            page=request.query_params.get("page", 1))
        return Response({"results": MarketplacePluginSerializer(plugins, many=True).data})


class PluginDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, plugin_id):
        plugin = MarketplaceService.get_plugin(plugin_id)
        if plugin is None or plugin.status not in ("published", "deprecated"):
            raise NotFound("Plugin not found")
        versions = PluginVersion.objects.filter(
            plugin_id=plugin.id, is_published=True).order_by("-created_at")
        data = MarketplacePluginSerializer(plugin).data
        data["versions"] = PluginVersionListSerializer(versions, many=True).data
        return Response(data)


class PluginVersionDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, plugin_id, version_id):
        version = PluginVersion.objects.filter(
            id=version_id, plugin_id=plugin_id, is_published=True).first()
        if version is None:
            raise NotFound("Version not found")
        return Response(PluginVersionSerializer(version).data)


# ── workspace install management ──────────────────────────────────────────────
class InstalledListView(APIView):
    def get(self, request):
        _member(request)
        qs = InstalledPlugin.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response({"results": InstalledPluginSerializer(qs, many=True).data})


class InstalledDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        ip = InstalledPlugin.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if ip is None:
            raise NotFound("Installed plugin not found")
        return Response(InstalledPluginSerializer(ip).data)


class PluginInstallView(APIView):
    def post(self, request, plugin_id):
        member = _member(request)
        version_id = request.data.get("version_id")
        if not version_id:
            raise ValidationError("version_id is required.")
        try:
            ip = MarketplaceService.install_plugin(
                plugin_id=plugin_id, version_id=version_id, workspace_id=_ws(request),
                installed_by=member.user_id)
        except MarketplaceError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(InstalledPluginSerializer(ip).data, status=201)


class PluginUninstallView(APIView):
    def post(self, request, pk):
        member = _member(request)
        try:
            ip = MarketplaceService.uninstall_plugin(
                installed_plugin_id=pk, workspace_id=_ws(request),
                actor_id=member.user_id, hard=bool(request.data.get("hard", False)))
        except MarketplaceError as exc:
            raise NotFound(str(exc)) from exc
        return Response(InstalledPluginSerializer(ip).data)


class PluginUpgradeView(APIView):
    def post(self, request, pk):
        member = _member(request)
        ip = InstalledPlugin.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if ip is None:
            raise NotFound("Installed plugin not found")
        version_id = request.data.get("version_id")
        if not version_id:
            raise ValidationError("version_id is required.")
        try:
            ip = MarketplaceService.upgrade_plugin(
                installed_plugin_id=ip.id, new_version_id=version_id, actor_id=member.user_id)
        except MarketplaceError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(InstalledPluginSerializer(ip).data)


class PluginRollbackView(APIView):
    def post(self, request, pk):
        member = _member(request)
        ip = InstalledPlugin.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if ip is None:
            raise NotFound("Installed plugin not found")
        try:
            ip = MarketplaceService.rollback_plugin(
                installed_plugin_id=ip.id, actor_id=member.user_id)
        except MarketplaceError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(InstalledPluginSerializer(ip).data)


# ── publisher management (is_staff) ───────────────────────────────────────────
class ManagePluginListView(APIView):
    def get(self, request):
        _require_staff(request)
        qs = MarketplacePlugin.objects.all().order_by("-created_at")
        return Response({"results": MarketplacePluginSerializer(qs, many=True).data})

    def post(self, request):
        _require_staff(request)
        ser = MarketplacePluginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(MarketplacePluginSerializer(obj).data, status=201)


class ManagePluginDetailView(APIView):
    def _get(self, request, pk) -> MarketplacePlugin:
        obj = MarketplacePlugin.objects.filter(id=pk).first()
        if obj is None:
            raise NotFound("Plugin not found")
        return obj

    def get(self, request, pk):
        _require_staff(request)
        return Response(MarketplacePluginSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_staff(request)
        obj = self._get(request, pk)
        ser = MarketplacePluginSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(MarketplacePluginSerializer(obj).data)


class ManagePluginPublishView(APIView):
    def post(self, request, pk):
        _require_staff(request)
        plugin = MarketplacePlugin.objects.filter(id=pk).first()
        if plugin is None:
            raise NotFound("Plugin not found")
        plugin.status = "published"
        plugin.save(update_fields=["status"])
        return Response(MarketplacePluginSerializer(plugin).data)


class ManagePluginDeprecateView(APIView):
    def post(self, request, pk):
        _require_staff(request)
        plugin = MarketplacePlugin.objects.filter(id=pk).first()
        if plugin is None:
            raise NotFound("Plugin not found")
        plugin.status = "deprecated"
        plugin.save(update_fields=["status"])
        return Response(MarketplacePluginSerializer(plugin).data)


class ManagePluginVersionCreateView(APIView):
    def post(self, request, pk):
        user = _require_staff(request)
        plugin = MarketplacePlugin.objects.filter(id=pk).first()
        if plugin is None:
            raise NotFound("Plugin not found")
        manifest = request.data.get("manifest")
        version = request.data.get("version")
        if not version or manifest is None:
            raise ValidationError("version and manifest are required.")
        errors = validate_manifest(manifest)
        if errors:
            raise ValidationError({"manifest": errors})
        if PluginVersion.objects.filter(plugin_id=plugin.id, version=version).exists():
            raise ValidationError("Version already exists.")
        from django.utils import timezone
        manifest_hash = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        pv = PluginVersion.objects.create(
            plugin_id=plugin.id, version=version, changelog=request.data.get("changelog", ""),
            manifest=manifest, manifest_hash=manifest_hash, is_published=True,
            published_at=timezone.now(), published_by=getattr(user, "id", None))
        MarketplacePlugin.objects.filter(id=plugin.id).update(latest_version=version)
        return Response(PluginVersionSerializer(pv).data, status=201)
