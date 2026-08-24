"""
Feature-flags API (Phase 1.29) — /api/v1/feature-flags/.

Reads of ``/active/`` are open to any workspace member (the shell reads resolved flags);
flag + override management is owner/admin only.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.services import _role_chain_ids

from . import services
from .models import FeatureFlag, FeatureFlagOverride
from .serializers import FeatureFlagOverrideSerializer, FeatureFlagSerializer

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
        raise PermissionDenied("Feature-flag management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _get_flag(ws, flag_id):
    flag = FeatureFlag.objects.filter(workspace_id=ws, id=flag_id).first()
    if flag is None:
        raise NotFound("Feature flag not found.")
    return flag


# ── Resolved flags for the caller ─────────────────────────────────────────────
class ActiveFlagsView(APIView):
    def get(self, request):
        member = _member(request)
        role_ids = _role_chain_ids(member)
        flags = services.resolve_flags(_ws(request), user_id=_uid(request), role_ids=role_ids)
        return Response({"flags": flags})


# ── Flag CRUD (admin) ─────────────────────────────────────────────────────────
class FlagListCreateView(APIView):
    def get(self, request):
        _require_admin(request)
        qs = FeatureFlag.objects.filter(workspace_id=_ws(request)).order_by("key")
        return Response(FeatureFlagSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = FeatureFlagSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if FeatureFlag.objects.filter(workspace_id=ws, key=ser.validated_data["key"]).exists():
            raise ValidationError(f"Flag {ser.validated_data['key']!r} already exists.")
        flag = ser.save(workspace_id=ws, created_by=_uid(request))
        return Response(FeatureFlagSerializer(flag).data, status=status.HTTP_201_CREATED)


class FlagDetailView(APIView):
    def get(self, request, flag_id):
        _require_admin(request)
        return Response(FeatureFlagSerializer(_get_flag(_ws(request), flag_id)).data)

    def patch(self, request, flag_id):
        _require_admin(request)
        flag = _get_flag(_ws(request), flag_id)
        ser = FeatureFlagSerializer(flag, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(FeatureFlagSerializer(flag).data)

    def delete(self, request, flag_id):
        _require_admin(request)
        _get_flag(_ws(request), flag_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Overrides (admin) ─────────────────────────────────────────────────────────
class OverrideListCreateView(APIView):
    def get(self, request, flag_id):
        _require_admin(request)
        flag = _get_flag(_ws(request), flag_id)
        return Response(FeatureFlagOverrideSerializer(flag.overrides.all(), many=True).data)

    def post(self, request, flag_id):
        _require_admin(request)
        ws = _ws(request)
        flag = _get_flag(ws, flag_id)
        ser = FeatureFlagOverrideSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if FeatureFlagOverride.objects.filter(
                workspace_id=ws, flag=flag, target_type=d["target_type"],
                target_id=d.get("target_id")).exists():
            raise ValidationError("An override for this target already exists.")
        ov = ser.save(workspace_id=ws, flag=flag, created_by=_uid(request))
        return Response(FeatureFlagOverrideSerializer(ov).data, status=status.HTTP_201_CREATED)


class OverrideDetailView(APIView):
    def delete(self, request, flag_id, override_id):
        _require_admin(request)
        ws = _ws(request)
        _get_flag(ws, flag_id)
        ov = FeatureFlagOverride.objects.filter(
            workspace_id=ws, flag_id=flag_id, id=override_id).first()
        if ov is None:
            raise NotFound("Override not found.")
        ov.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
