"""
Relationship builder API (Phase 1.7) — endpoints under ``/api/v1/relationships/``.

Workspace scoping comes from ``request.workspace_id`` (TenantMiddleware). All schema
provisioning is delegated to ``RelationshipService`` → ``SchemaRegistryService``.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    LinkSerializer,
    RelationshipCreateSerializer,
    RelationshipOutputSerializer,
)
from .services import (
    RelationshipNotFoundError,
    RelationshipService,
    RelationshipValidationError,
)


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _uid(request):
    return getattr(request.user, "id", None)


def _handle(exc):
    if isinstance(exc, RelationshipNotFoundError):
        raise NotFound(str(exc))
    raise ValidationError(str(exc))


class RelationshipListCreateView(APIView):
    def get(self, request):
        entity_id = request.query_params.get("entity_id")
        rels = RelationshipService.list_relationships(workspace_id=_ws(request), entity_id=entity_id)
        return Response(RelationshipOutputSerializer(rels, many=True).data)

    def post(self, request):
        ser = RelationshipCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            rel = RelationshipService.create_relationship(
                workspace_id=_ws(request), name=d["name"], slug=d["slug"],
                source_entity_id=d["source_entity_id"], target_entity_id=d["target_entity_id"],
                cardinality=d["cardinality"], on_delete=d.get("on_delete", "detach"),
                source_field_slug=d.get("source_field_slug") or None, created_by=_uid(request))
        except (RelationshipValidationError, RelationshipNotFoundError) as exc:
            _handle(exc)
        return Response(RelationshipOutputSerializer(rel).data, status=status.HTTP_201_CREATED)


class RelationshipDetailView(APIView):
    def get(self, request, relationship_id):
        try:
            rel = RelationshipService.get_relationship(
                workspace_id=_ws(request), relationship_id=relationship_id)
        except RelationshipNotFoundError as exc:
            _handle(exc)
        return Response(RelationshipOutputSerializer(rel).data)

    def delete(self, request, relationship_id):
        try:
            RelationshipService.delete_relationship(
                workspace_id=_ws(request), relationship_id=relationship_id, deleted_by=_uid(request))
        except RelationshipNotFoundError as exc:
            _handle(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RelationshipLinkView(APIView):
    """Create/remove instance links (many-to-many / flexible cross-entity links)."""

    def post(self, request, relationship_id):
        ser = LinkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            link = RelationshipService.link_records(
                workspace_id=_ws(request), relationship_id=relationship_id,
                source_record_id=ser.validated_data["source_record_id"],
                target_record_id=ser.validated_data["target_record_id"],
                created_by=_uid(request))
        except RelationshipNotFoundError as exc:
            _handle(exc)
        return Response({"id": str(link.id)}, status=status.HTTP_201_CREATED)

    def delete(self, request, relationship_id):
        ser = LinkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            removed = RelationshipService.unlink_records(
                workspace_id=_ws(request), relationship_id=relationship_id,
                source_record_id=ser.validated_data["source_record_id"],
                target_record_id=ser.validated_data["target_record_id"])
        except RelationshipNotFoundError as exc:
            _handle(exc)
        return Response({"removed": removed}, status=status.HTTP_200_OK)
