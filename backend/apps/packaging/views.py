"""
Solution Package Platform REST API at /api/v1/packages/.

Read surfaces (catalog registry, core capabilities, dependency matrix, preflight) are open to
any workspace member. Lifecycle mutations (upgrade / rollback / enable / disable) require
owner/admin — they change what is provisioned in the workspace. All provisioning still runs
through ``solution_templates.services`` (the single installer); this API is the platform's
registry + governance layer over it.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.solution_templates import services as sol

from . import registry
from .preflight import preflight

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


class CatalogView(APIView):
    def get(self, request):
        _member(request)
        return Response(registry.list_catalog(
            category=request.query_params.get("category"),
            search=request.query_params.get("search")))


class CoreView(APIView):
    """Platform version + the single shared engines + capabilities a package may require."""

    def get(self, request):
        _member(request)
        return Response(registry.core())


class DependencyMatrixView(APIView):
    def get(self, request):
        _member(request)
        return Response({"core_version": registry.core()["core_version"],
                         "packages": registry.dependency_matrix()})


class PreflightView(APIView):
    """Dry-run the install gate for a manifest or catalog template. Nothing is installed."""

    def get(self, request):  # convenience: preflight a catalog template by id
        _member(request)
        template_id = request.query_params.get("template_id")
        if not template_id:
            return Response({"detail": "template_id is required."}, status=400)
        return self._run_template(request, template_id)

    def post(self, request):
        _member(request)
        template_id = request.data.get("template_id")
        if template_id:
            return self._run_template(request, template_id)
        manifest = request.data.get("manifest")
        if not isinstance(manifest, dict):
            return Response({"detail": "Provide a manifest object or a template_id."}, status=400)
        return Response(preflight(manifest, workspace_id=_ws(request)).as_dict())

    def _run_template(self, request, template_id):
        try:
            tpl = sol.get_template(template_id)
        except sol.SolutionTemplateError:
            return Response({"detail": "Template not found."}, status=404)
        return Response(preflight(tpl.manifest, workspace_id=_ws(request)).as_dict())


class InstalledRegistryView(APIView):
    def get(self, request):
        _member(request)
        return Response(registry.list_installed(workspace_id=_ws(request)))


class UpgradeView(APIView):
    def post(self, request, installed_id):
        _require_admin(request)
        try:
            sol.upgrade(
                installed_id=installed_id, workspace_id=_ws(request),
                actor_id=getattr(request.user, "id", None),
                to_template_id=request.data.get("template_id"),
                manifest=request.data.get("manifest"),
                version=request.data.get("version"))
        except sol.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(registry.list_installed(workspace_id=_ws(request)))


class RollbackView(APIView):
    def post(self, request, installed_id):
        _require_admin(request)
        try:
            sol.rollback(installed_id=installed_id, workspace_id=_ws(request),
                         actor_id=getattr(request.user, "id", None))
        except sol.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(registry.list_installed(workspace_id=_ws(request)))


class EnableView(APIView):
    def post(self, request, installed_id):
        _require_admin(request)
        try:
            sol.enable(installed_id=installed_id, workspace_id=_ws(request),
                       actor_id=getattr(request.user, "id", None))
        except sol.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(registry.list_installed(workspace_id=_ws(request)))


class DisableView(APIView):
    """Soft uninstall (disable) — workflows archived, apps unpublished, data preserved."""

    def post(self, request, installed_id):
        _require_admin(request)
        try:
            sol.uninstall(installed_id=installed_id, workspace_id=_ws(request),
                          actor_id=getattr(request.user, "id", None),
                          hard=bool(request.data.get("hard", False)))
        except sol.SolutionTemplateError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(registry.list_installed(workspace_id=_ws(request)))
