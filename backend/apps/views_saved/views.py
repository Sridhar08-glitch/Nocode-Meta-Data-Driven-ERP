"""Saved Views API — /api/v1/saved-views/."""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from . import services


def _ctx(request):
    ws = getattr(request, "workspace_id", None)
    member = getattr(request, "workspace_member", None)
    if not ws or member is None:
        raise PermissionDenied("No active workspace membership.")
    return (ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))), member.id


def _json(v):
    return {
        "id": str(v.id), "entity_id": str(v.entity_id), "name": v.name,
        "hidden_field_slugs": v.hidden_field_slugs, "column_widths": v.column_widths,
        "personal_filters": v.personal_filters, "sort_overrides": v.sort_overrides,
        "group_by_override": v.group_by_override, "is_pinned": v.is_pinned,
    }


class SavedViewListCreateView(APIView):
    def get(self, request):
        ws, member_id = _ctx(request)
        entity_id = None
        slug = request.query_params.get("entity_slug")
        if slug:
            try:
                entity_id = SchemaRegistryService.get_entity(workspace_id=ws, slug=slug).id
            except EntityNotFoundError as exc:
                raise NotFound(str(exc)) from exc
        views = services.list_for_member(workspace_id=ws, member_id=member_id, entity_id=entity_id)
        return Response({"results": [_json(v) for v in views], "count": len(views)})

    def post(self, request):
        ws, member_id = _ctx(request)
        slug = request.data.get("entity_slug")
        if not slug:
            raise ValidationError("entity_slug is required")
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=ws, slug=slug)
        except EntityNotFoundError as exc:
            raise NotFound(str(exc)) from exc
        view = services.create_saved_view(workspace_id=ws, member_id=member_id,
                                          entity_id=entity.id, data=request.data)
        return Response(_json(view), status=status.HTTP_201_CREATED)


class SavedViewDetailView(APIView):
    def _get(self, request, view_id):
        ws, member_id = _ctx(request)
        view = services.get_owned(workspace_id=ws, member_id=member_id, view_id=view_id)
        if view is None:
            raise NotFound("Saved view not found")
        return view

    def get(self, request, view_id):
        return Response(_json(self._get(request, view_id)))

    def patch(self, request, view_id):
        view = services.update_saved_view(self._get(request, view_id), request.data)
        return Response(_json(view))

    def delete(self, request, view_id):
        self._get(request, view_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
