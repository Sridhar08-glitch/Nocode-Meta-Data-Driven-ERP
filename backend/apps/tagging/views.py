"""Tagging API — /api/v1/tags/."""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from . import services


def _ws(request):
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_write(request):
    """Tag mutations require a write role — a read-only viewer cannot tag records."""
    role = getattr(getattr(request, "workspace_member", None), "role", "")
    if role not in ("owner", "admin", "member"):
        raise PermissionDenied("Write access required to modify tags.")


def _tag_json(t):
    return {"id": str(t.id), "name": t.name, "slug": t.slug, "color": t.color, "group": t.group}


class TagListCreateView(APIView):
    def get(self, request):
        tags = services.list_tags(workspace_id=_ws(request))
        return Response({"results": [_tag_json(t) for t in tags], "count": len(tags)})

    def post(self, request):
        _require_write(request)
        d = request.data
        if not d.get("slug") or not d.get("name"):
            raise ValidationError("name and slug are required")
        tag = services.create_tag(workspace_id=_ws(request), name=d["name"], slug=d["slug"],
                                  color=d.get("color", "#6366f1"), group=d.get("group", ""))
        return Response(_tag_json(tag), status=status.HTTP_201_CREATED)


class RecordTagsView(APIView):
    def _entity(self, ws, slug):
        try:
            return SchemaRegistryService.get_entity(workspace_id=ws, slug=slug)
        except EntityNotFoundError as exc:
            raise NotFound(str(exc)) from exc

    def get(self, request):
        ws = _ws(request)
        record_id = request.query_params.get("record_id")
        if not record_id:
            raise ValidationError("record_id is required")
        tags = services.tags_for_record(workspace_id=ws, record_id=record_id)
        return Response({"results": [_tag_json(t) for t in tags], "count": len(tags)})

    def post(self, request):
        _require_write(request)
        ws = _ws(request)
        entity = self._entity(ws, request.data.get("entity_slug", ""))
        tag_id = request.data.get("tag_id")
        record_id = request.data.get("record_id")
        if not tag_id or not record_id:
            raise ValidationError("tag_id and record_id are required")
        services.attach(workspace_id=ws, tag_id=tag_id, entity_id=entity.id, record_id=record_id,
                        by=getattr(request.user, "id", None))
        return Response({"detail": "attached"}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        _require_write(request)
        ws = _ws(request)
        tag_id = request.data.get("tag_id")
        record_id = request.data.get("record_id")
        if not tag_id or not record_id:
            raise ValidationError("tag_id and record_id are required")
        n = services.detach(workspace_id=ws, tag_id=tag_id, record_id=record_id,
                            by=getattr(request.user, "id", None))
        return Response({"removed": n})
