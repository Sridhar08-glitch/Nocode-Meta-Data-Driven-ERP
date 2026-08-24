"""
Email-templates API (Phase 1.33) — /api/v1/templates/email/.

Reads = any member; create/update/delete + test-send = owner/admin. Workspace-scoped.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import EmailTemplate
from .serializers import EmailTemplateSerializer

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
        raise PermissionDenied("Email-template editing requires an admin or owner role.")


def _get(request, pk) -> EmailTemplate:
    obj = EmailTemplate.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if obj is None:
        raise NotFound("Email template not found.")
    return obj


class EmailTemplateListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = EmailTemplate.objects.filter(workspace_id=_ws(request)).order_by("slug", "locale")
        return Response({"results": EmailTemplateSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ser = EmailTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        d = ser.validated_data
        if EmailTemplate.objects.filter(
                workspace_id=ws, slug=d["slug"], locale=d.get("locale", "en")).exists():
            raise ValidationError("A template with this slug+locale already exists.")
        obj = ser.save(workspace_id=ws, created_by=getattr(request.user, "id", None))
        return Response(EmailTemplateSerializer(obj).data, status=status.HTTP_201_CREATED)


class EmailTemplateDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(EmailTemplateSerializer(_get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = _get(request, pk)
        ser = EmailTemplateSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        services.apply_version_bump(obj, ser.validated_data)
        ser.save()
        return Response(EmailTemplateSerializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        _get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailTemplateRenderView(APIView):
    def post(self, request, pk):
        _member(request)
        obj = _get(request, pk)
        return Response(services.render(obj, request.data.get("context") or {}))


class EmailTemplateTestSendView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        obj = _get(request, pk)
        try:
            result = services.test_send(
                obj, to_email=request.data.get("to_email"),
                context=request.data.get("context") or {})
        except services.EmailTemplateError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)
