"""
System-Entity Adapter (B0) REST at /api/v1/system-entities/ — the metadata-shaped surface the Generic
Runtime consumes for native-model engines (parallels /metadata/entities/ + /data/{slug}/).
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import SystemEntityError, SystemEntityService


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _role(request):
    m = getattr(request, "workspace_member", None)
    return getattr(m, "role", None) if m is not None else None


def _uid(request):
    return getattr(request.user, "id", None)


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except SystemEntityError as exc:
        raise NotFound(str(exc)) from exc


class EntityListView(APIView):
    def get(self, request):
        return Response(SystemEntityService.list_entities(
            workspace_id=_ws(request), role=_role(request)))


class EntityDescriptorView(APIView):
    def get(self, request, slug):
        return Response(_guard(SystemEntityService.descriptor, slug=slug, role=_role(request)))


class RecordListView(APIView):
    def get(self, request, slug):
        qp = request.query_params
        reserved = {"sort", "page", "page_size"}
        filters = {k: v for k, v in qp.items() if k not in reserved}
        return Response(_guard(
            SystemEntityService.list_records, slug=slug, workspace_id=_ws(request),
            role=_role(request), filters=filters, sort=qp.get("sort"),
            page=qp.get("page", 1), page_size=qp.get("page_size", 50)))

    def post(self, request, slug):
        try:
            row = SystemEntityService.create(
                slug=slug, workspace_id=_ws(request), role=_role(request),
                data=request.data or {}, actor_id=_uid(request))
        except SystemEntityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(row, status=201)


class RecordDetailView(APIView):
    def get(self, request, slug, record_id):
        return Response(_guard(
            SystemEntityService.retrieve, slug=slug, workspace_id=_ws(request),
            role=_role(request), record_id=record_id))

    def patch(self, request, slug, record_id):
        try:
            return Response(SystemEntityService.update(
                slug=slug, workspace_id=_ws(request), role=_role(request),
                record_id=record_id, data=request.data or {}, actor_id=_uid(request)))
        except SystemEntityError as exc:
            raise ValidationError(str(exc)) from exc

    def delete(self, request, slug, record_id):
        try:
            SystemEntityService.delete(
                slug=slug, workspace_id=_ws(request), role=_role(request),
                record_id=record_id, actor_id=_uid(request))
        except SystemEntityError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(status=204)
