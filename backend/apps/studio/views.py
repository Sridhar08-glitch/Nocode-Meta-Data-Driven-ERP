"""
Studio API (Phase 1.32) — Applications, Home Layouts, Navigation.

Reads + switcher/resolve are open to any active member; create/update/delete/publish are
owner/admin only. All objects are workspace-scoped (RLS-backed); resolve endpoints honour
the caller's role tokens.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.services import _role_chain_ids

from . import services
from .models import Application, HomeLayout, Navigation
from .serializers import (
    ApplicationSerializer,
    HomeLayoutSerializer,
    NavigationSerializer,
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
        raise PermissionDenied("Studio editing requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _get(model, request, pk):
    obj = model.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if obj is None:
        raise NotFound(f"{model.__name__} not found.")
    return obj


# ── generic CRUD base ─────────────────────────────────────────────────────────
class _StudioListCreate(APIView):
    model = None
    serializer = None
    unique_slug = False

    def get(self, request):
        _member(request)
        qs = self.model.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response({"results": self.serializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if self.unique_slug and self.model.objects.filter(
                workspace_id=ws, slug=ser.validated_data.get("slug")).exists():
            raise ValidationError("An object with this slug already exists.")
        obj = ser.save(workspace_id=ws, created_by=_uid(request))
        return Response(self.serializer(obj).data, status=status.HTTP_201_CREATED)


class _StudioDetail(APIView):
    model = None
    serializer = None

    def get(self, request, pk):
        _member(request)
        return Response(self.serializer(_get(self.model, request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = _get(self.model, request, pk)
        ser = self.serializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(self.serializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        _get(self.model, request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class _PublishView(APIView):
    model = None
    serializer = None

    def post(self, request, pk):
        _require_admin(request)
        obj = _get(self.model, request, pk)
        obj.is_published = True
        obj.save(update_fields=["is_published", "updated_at"])
        return Response(self.serializer(obj).data)


# ── Applications ──────────────────────────────────────────────────────────────
class ApplicationListCreateView(_StudioListCreate):
    model = Application
    serializer = ApplicationSerializer
    unique_slug = True


class ApplicationDetailView(_StudioDetail):
    model = Application
    serializer = ApplicationSerializer


class ApplicationPublishView(_PublishView):
    model = Application
    serializer = ApplicationSerializer


class ApplicationSwitcherView(APIView):
    def get(self, request):
        member = _member(request)
        apps = services.app_switcher(
            workspace_id=_ws(request), tokens=services.role_tokens(member))
        return Response({"results": ApplicationSerializer(apps, many=True).data,
                         "count": len(apps)})


# ── Home Layouts ──────────────────────────────────────────────────────────────
class HomeLayoutListCreateView(_StudioListCreate):
    model = HomeLayout
    serializer = HomeLayoutSerializer


class HomeLayoutDetailView(_StudioDetail):
    model = HomeLayout
    serializer = HomeLayoutSerializer


class HomeLayoutPublishView(_PublishView):
    model = HomeLayout
    serializer = HomeLayoutSerializer


class HomeLayoutResolveView(APIView):
    def get(self, request):
        member = _member(request)
        layout = services.resolve_home_layout(
            workspace_id=_ws(request), user_id=_uid(request),
            role_ids=_role_chain_ids(member),
            app_id=request.query_params.get("app"))
        return Response(HomeLayoutSerializer(layout).data if layout else {})


# ── Navigation ────────────────────────────────────────────────────────────────
class NavigationListCreateView(_StudioListCreate):
    model = Navigation
    serializer = NavigationSerializer


class NavigationDetailView(_StudioDetail):
    model = Navigation
    serializer = NavigationSerializer


class NavigationPublishView(_PublishView):
    model = Navigation
    serializer = NavigationSerializer


class NavigationResolveView(APIView):
    def get(self, request):
        member = _member(request)
        nav = services.resolve_navigation(
            workspace_id=_ws(request), tokens=services.role_tokens(member),
            app_id=request.query_params.get("app"))
        return Response(nav or {})
