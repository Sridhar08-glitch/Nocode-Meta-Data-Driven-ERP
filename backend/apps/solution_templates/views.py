"""
Solution Template Framework REST API (Phase P2.4A) at /api/v1/solution-templates/.

Browse + preview are open to any workspace member; installing/uninstalling a solution into
the workspace requires owner/admin. Authoring catalog templates (create/publish) is staff-only
(the curated, global catalog), mirroring the marketplace/process-catalog publisher gate.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services, wizard
from .library import get_library
from .models import SolutionTemplate
from .serializers import (
    InstalledSolutionSerializer,
    SolutionTemplateSerializer,
    SolutionTemplateWriteSerializer,
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
        raise PermissionDenied("Installing a solution requires an admin or owner role.")


def _require_staff(request):
    if not getattr(request.user, "is_staff", False):
        raise PermissionDenied("Managing the solution catalog requires staff access.")


# ── catalog browse + author ──────────────────────────────────────────────────
class TemplateListView(APIView):
    def get(self, request):
        rows = services.list_templates(
            category=request.query_params.get("category"),
            search=request.query_params.get("search"))
        return Response(SolutionTemplateSerializer(rows, many=True).data)

    def post(self, request):
        _require_staff(request)
        ser = SolutionTemplateWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tpl = SolutionTemplate.objects.create(**ser.validated_data)
        return Response(SolutionTemplateSerializer(tpl).data, status=201)


class LibraryView(APIView):
    """The standard building-block library (objects / workflows / roles / dashboards / reports)."""

    def get(self, request):
        _member(request)
        return Response(get_library())


class TemplateDetailView(APIView):
    def get(self, request, template_id):
        _member(request)
        try:
            tpl = services.get_template(template_id)
        except services.SolutionTemplateError:
            return Response({"detail": "Not found."}, status=404)
        return Response(services.preview(tpl))


class TemplateInstallView(APIView):
    def post(self, request, template_id):
        _require_admin(request)
        try:
            installed = services.install(
                template_id=template_id, workspace_id=_ws(request),
                installed_by=getattr(request.user, "id", None))
        except services.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(InstalledSolutionSerializer(installed).data, status=201)


class TemplatePublishView(APIView):
    def post(self, request, template_id):
        _require_staff(request)
        tpl = SolutionTemplate.objects.filter(id=template_id).first()
        if tpl is None:
            return Response({"detail": "Not found."}, status=404)
        tpl.is_published = True
        tpl.save(update_fields=["is_published", "updated_at"])
        return Response(SolutionTemplateSerializer(tpl).data)


# ── installed solutions ──────────────────────────────────────────────────────
class InstalledListView(APIView):
    def get(self, request):
        rows = services.list_installed(workspace_id=_ws(request))
        return Response(InstalledSolutionSerializer(rows, many=True).data)


class InstalledUninstallView(APIView):
    def post(self, request, installed_id):
        _require_admin(request)
        try:
            obj = services.uninstall(
                installed_id=installed_id, workspace_id=_ws(request),
                actor_id=getattr(request.user, "id", None),
                hard=bool(request.data.get("hard", False)))
        except services.SolutionTemplateError:
            return Response({"detail": "Not found."}, status=404)
        return Response(InstalledSolutionSerializer(obj).data)


# ── Create Solution Wizard (P2.4B) ───────────────────────────────────────────
class WizardOptionsView(APIView):
    """Solution types + industry presets + the standard library for the wizard UI."""

    def get(self, request):
        _member(request)
        return Response(wizard.options())


class WizardResolveView(APIView):
    """Resolve a chosen object set to include its lookup dependencies (live UX)."""

    def post(self, request):
        _member(request)
        objs = request.data.get("business_objects", []) or []
        return Response({"resolved_objects": wizard.resolve_dependencies(objs)})


class WizardPreviewView(APIView):
    """Compose + validate the manifest and surface collision/dependency warnings.
    Nothing is installed. Any member may preview."""

    def post(self, request):
        _member(request)
        result = wizard.preview(
            request.data or {}, workspace_id=_ws(request),
            actor_id=getattr(request.user, "id", None))
        return Response(result)


class WizardCreateView(APIView):
    """Provision the solution through the authoritative installer. Owner/admin only."""

    def post(self, request):
        _require_admin(request)
        try:
            installed = wizard.create(
                request.data or {}, workspace_id=_ws(request),
                actor_id=getattr(request.user, "id", None))
        except services.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(InstalledSolutionSerializer(installed).data, status=201)
