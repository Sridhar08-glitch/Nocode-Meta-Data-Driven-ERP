"""
Document-templates API (Phase 1.33) — /api/v1/templates/documents/.

Reads = any member; create/update/delete = owner/admin. ``render/?record_id=`` returns a
PDF (the bound record is fetched through RecordService, so RBAC/ABAC/masking apply).
"""
import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.services import PermissionError as NexusPermissionError
from apps.records.services import EntityNotQueryable, RecordNotFound

from . import services
from .models import DocumentTemplate
from .serializers import DocumentTemplateSerializer

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
        raise PermissionDenied("Document-template editing requires an admin or owner role.")


def _get(request, pk) -> DocumentTemplate:
    obj = DocumentTemplate.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if obj is None:
        raise NotFound("Document template not found.")
    return obj


class DocumentTemplateListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = DocumentTemplate.objects.filter(workspace_id=_ws(request)).order_by("slug")
        return Response({"results": DocumentTemplateSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ser = DocumentTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if DocumentTemplate.objects.filter(
                workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A template with this slug already exists.")
        obj = ser.save(workspace_id=ws, created_by=getattr(request.user, "id", None))
        return Response(DocumentTemplateSerializer(obj).data, status=status.HTTP_201_CREATED)


class DocumentTemplateDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(DocumentTemplateSerializer(_get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = _get(request, pk)
        ser = DocumentTemplateSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        services.apply_version_bump(obj, ser.validated_data)
        ser.save()
        return Response(DocumentTemplateSerializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        _get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentTemplateRenderView(APIView):
    def get(self, request, pk):
        member = _member(request)
        template = _get(request, pk)
        record_id = request.query_params.get("record_id")
        if not record_id:
            raise ParseError("record_id query parameter is required.")
        try:
            pdf = services.render(template, workspace_id=_ws(request),
                                  record_id=record_id, member=member)
        except (EntityNotQueryable, RecordNotFound) as exc:
            raise NotFound(str(exc)) from exc
        except NexusPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{template.slug}.pdf"'
        return resp
