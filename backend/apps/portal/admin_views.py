"""
Custom-admin Portal Builder API (Phase F3.7) — /api/v1/portal/admin/.

Lets a workspace owner/admin define the portal (config + branding), provision portal users
(separate auth realm) and their per-entity grants. NOT Django admin. Workspace-scoped; the portal
user password is hashed on write and never returned. PortalEntityGrant.link_field is the
server-enforced row scope (a portal user only ever sees records linked to them).
"""
import uuid

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .admin_serializers import (
    PortalConfigurationSerializer,
    PortalEntityGrantSerializer,
    PortalUserSerializer,
)
from .models import PortalConfiguration, PortalEntityGrant, PortalUser

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    member = getattr(request, "workspace_member", None)
    if member is None or getattr(member, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Portal administration requires an owner or admin role.")


# ── Configuration (one per workspace) ───────────────────────────────────────────
class PortalConfigView(APIView):
    def get(self, request):
        _require_admin(request)
        ws = _ws(request)
        cfg, _ = PortalConfiguration.objects.get_or_create(
            workspace_id=ws, defaults={"name": "Customer Portal"})
        return Response(PortalConfigurationSerializer(cfg).data)

    def patch(self, request):
        _require_admin(request)
        ws = _ws(request)
        cfg, _ = PortalConfiguration.objects.get_or_create(
            workspace_id=ws, defaults={"name": "Customer Portal"})
        ser = PortalConfigurationSerializer(cfg, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(PortalConfigurationSerializer(cfg).data)


# ── Portal users ────────────────────────────────────────────────────────────────
class PortalUserListCreateView(APIView):
    def get(self, request):
        _require_admin(request)
        qs = PortalUser.objects.filter(workspace_id=_ws(request)).order_by("email")
        return Response({"results": PortalUserSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = PortalUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        password = ser.validated_data.pop("password", None)
        if not password:
            raise ValidationError("A password is required to create a portal user.")
        email = ser.validated_data["email"].lower()
        if PortalUser.objects.filter(workspace_id=ws, email=email).exists():
            raise ValidationError("A portal user with this email already exists.")
        user = PortalUser.objects.create(
            workspace_id=ws, password_hash=make_password(password),
            is_verified=True,  # admin-provisioned accounts can sign in immediately
            **{**ser.validated_data, "email": email})
        return Response(PortalUserSerializer(user).data, status=status.HTTP_201_CREATED)


class PortalUserDetailView(APIView):
    def _get(self, request, pk):
        obj = PortalUser.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Portal user not found.")
        return obj

    def get(self, request, pk):
        _require_admin(request)
        return Response(PortalUserSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        user = self._get(request, pk)
        ser = PortalUserSerializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        password = ser.validated_data.pop("password", None)
        if password:
            user.password_hash = make_password(password)
        for k, v in ser.validated_data.items():
            setattr(user, k, v.lower() if k == "email" else v)
        user.save()
        return Response(PortalUserSerializer(user).data)

    def delete(self, request, pk):
        _require_admin(request)
        self._get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Entity grants ────────────────────────────────────────────────────────────────
class PortalGrantListCreateView(APIView):
    def get(self, request):
        _require_admin(request)
        qs = PortalEntityGrant.objects.filter(workspace_id=_ws(request)).order_by("entity_slug")
        return Response({"results": PortalEntityGrantSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = PortalEntityGrantSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if PortalEntityGrant.objects.filter(
                workspace_id=ws, entity_slug=d["entity_slug"],
                portal_type=d.get("portal_type", "")).exists():
            raise ValidationError("A grant for this entity + portal type already exists.")
        grant = ser.save(workspace_id=ws)
        return Response(PortalEntityGrantSerializer(grant).data, status=status.HTTP_201_CREATED)


class PortalGrantDetailView(APIView):
    def delete(self, request, pk):
        _require_admin(request)
        grant = PortalEntityGrant.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if grant is None:
            raise NotFound("Grant not found.")
        grant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
