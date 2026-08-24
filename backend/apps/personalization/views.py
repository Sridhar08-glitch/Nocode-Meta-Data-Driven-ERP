"""
Personalization API (Phase P0) — /api/v1/me/.

Per-user appearance & accessibility preferences for the authenticated caller in the
active workspace. There is no admin surface here: workspace governance (the lock
policy) lives on ``WorkspaceBranding.locked_fields`` under /api/v1/branding/.

  GET  /api/v1/me/appearance/         resolved effective appearance (feeds applyBranding)
  GET  /api/v1/me/preferences/        raw user overrides + the preference catalogue
  PUT  /api/v1/me/preferences/        upsert overrides (validated; locked keys → 403)
  POST /api/v1/me/preferences/reset/  clear all or given keys → revert to inherited
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.services import _role_chain_ids

from . import registry, services


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


def _uid(request):
    return getattr(request.user, "id", None)


class AppearanceView(APIView):
    """GET /api/v1/me/appearance/ — resolved effective appearance for the caller."""

    def get(self, request):
        member = _member(request)
        role_ids = _role_chain_ids(member)
        data = services.resolve_appearance(_ws(request), user_id=_uid(request), role_ids=role_ids)
        return Response(data)


class PreferencesView(APIView):
    """GET/PUT /api/v1/me/preferences/ — the caller's raw overrides."""

    def get(self, request):
        _member(request)
        return Response({
            "values": services.get_user_values(_ws(request), _uid(request)),
            "registry": registry.public_catalogue(),
        })

    def put(self, request):
        _member(request)
        incoming = request.data.get("values", request.data)
        try:
            values = services.set_user_values(_ws(request), _uid(request), incoming)
        except services.LockedPreferenceError as exc:
            raise PermissionDenied(str(exc)) from exc
        except registry.PersonalizationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"values": values})


class PreferencesResetView(APIView):
    """POST /api/v1/me/preferences/reset/ — clear all or given keys."""

    def post(self, request):
        _member(request)
        keys = request.data.get("keys")
        try:
            values = services.reset_user_values(_ws(request), _uid(request), keys=keys)
        except registry.PersonalizationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"values": values})
