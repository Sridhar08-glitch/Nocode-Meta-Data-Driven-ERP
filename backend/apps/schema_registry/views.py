"""
Schema Registry — API Views
============================

REST endpoints for managing entity schemas and their field definitions.

URL design (all rooted under ``/api/schema/``):
  POST   /api/schema/entities/                              create_entity
  GET    /api/schema/entities/{slug}/                       get_entity
  POST   /api/schema/entities/{slug}/fields/                add_field
  PATCH  /api/schema/entities/{slug}/fields/{field_slug}/   update_field
  DELETE /api/schema/entities/{slug}/fields/{field_slug}/   remove_field
  GET    /api/schema/entities/{slug}/versions/              list_versions
  GET    /api/schema/entities/{slug}/diff/                  diff_versions
  POST   /api/schema/entities/{slug}/rollback/              rollback

All views extract ``workspace_id`` from ``request.user.workspace_id``
(set by TenantJWTMiddleware from the RS256 JWT).

No AI, no async, no stubs.
"""
from __future__ import annotations

import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schema_registry.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    FieldAlreadyExistsError,
    FieldNotFoundError,
    InvalidFieldTypeError,
    InvalidSlugError,
    RollbackError,
    SchemaRegistryError,
    SchemaVersionNotFoundError,
    SystemFieldError,
)
from apps.schema_registry.serializers import (
    AddFieldSerializer,
    CreateEntitySerializer,
    DiffVersionsSerializer,
    EntityDefinitionOutputSerializer,
    FieldDefinitionOutputSerializer,
    RollbackSerializer,
    SchemaVersionOutputSerializer,
    UpdateFieldSerializer,
)
from apps.schema_registry.services import SchemaRegistryService


def _workspace_id(request: Request) -> uuid.UUID:
    """Extract workspace_id from the authenticated request."""
    ws = getattr(request.user, "workspace_id", None)
    if not ws:
        raise PermissionDenied("workspace_id missing from JWT claims.")
    if isinstance(ws, str):
        ws = uuid.UUID(ws)
    return ws


def _acting_user(request: Request):
    """Return user UUID or None."""
    uid = getattr(request.user, "id", None) or getattr(request.user, "pk", None)
    if uid and not isinstance(uid, uuid.UUID):
        try:
            uid = uuid.UUID(str(uid))
        except (ValueError, AttributeError):
            uid = None
    return uid


def _map_exception(exc: SchemaRegistryError):
    """Map domain exceptions to DRF HTTP responses."""
    if isinstance(exc, EntityNotFoundError | FieldNotFoundError | SchemaVersionNotFoundError):
        raise NotFound(str(exc))
    if isinstance(exc, EntityAlreadyExistsError | FieldAlreadyExistsError):
        raise ValidationError(str(exc))
    if isinstance(exc, InvalidSlugError | InvalidFieldTypeError):
        raise ValidationError(str(exc))
    if isinstance(exc, SystemFieldError):
        raise PermissionDenied(str(exc))
    if isinstance(exc, RollbackError):
        raise ValidationError(str(exc))
    # Generic fallback
    raise ValidationError(str(exc))


# ---------------------------------------------------------------------------
# Entity views
# ---------------------------------------------------------------------------

class EntityListView(APIView):
    """
    POST /api/schema/entities/
      Create a new entity and provision its physical table.

    Body: CreateEntitySerializer shape
    Returns: 201 + EntityDefinitionOutputSerializer
    """

    def post(self, request: Request) -> Response:
        ser = CreateEntitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        workspace_id = _workspace_id(request)
        acting_user = _acting_user(request)

        try:
            entity = SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug=data["slug"],
                name=data["name"],
                plural_name=data["plural_name"],
                description=data.get("description", ""),
                fields=data.get("fields") or [],
                settings=data.get("settings") or {},
                title_field_slug=data.get("title_field_slug", "name"),
                created_by=acting_user,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        out = EntityDefinitionOutputSerializer(entity)
        return Response(out.data, status=status.HTTP_201_CREATED)


class EntityDetailView(APIView):
    """
    GET /api/schema/entities/{slug}/
      Return full entity schema including all field definitions.
    """

    def get(self, request: Request, slug: str) -> Response:
        workspace_id = _workspace_id(request)
        try:
            schema = SchemaRegistryService.get_entity_schema(
                workspace_id=workspace_id,
                slug=slug,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        return Response(schema, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Field views
# ---------------------------------------------------------------------------

class FieldListView(APIView):
    """
    POST /api/schema/entities/{slug}/fields/
      Add a new field to an existing entity.
    """

    def post(self, request: Request, slug: str) -> Response:
        ser = AddFieldSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        workspace_id = _workspace_id(request)
        acting_user = _acting_user(request)

        try:
            fd = SchemaRegistryService.add_field(
                workspace_id=workspace_id,
                entity_slug=slug,
                slug=data["slug"],
                name=data["name"],
                field_type=data["field_type"],
                description=data.get("description", ""),
                is_promoted=data.get("is_promoted", False),
                is_filterable=data.get("is_filterable", True),
                is_sortable=data.get("is_sortable", True),
                is_searchable=data.get("is_searchable", False),
                has_index=data.get("has_index", False),
                is_required=data.get("is_required", False),
                is_unique=data.get("is_unique", False),
                default_value=data.get("default_value"),
                config=data.get("config") or {},
                order=data.get("order", 0),
                read_roles=data.get("read_roles") or [],
                write_roles=data.get("write_roles") or [],
                updated_by=acting_user,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        out = FieldDefinitionOutputSerializer(fd)
        return Response(out.data, status=status.HTTP_201_CREATED)


class FieldDetailView(APIView):
    """
    PATCH  /api/schema/entities/{slug}/fields/{field_slug}/   update_field
    DELETE /api/schema/entities/{slug}/fields/{field_slug}/   remove_field
    """

    def patch(self, request: Request, slug: str, field_slug: str) -> Response:
        ser = UpdateFieldSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        updates = ser.validated_data

        if not updates:
            raise ValidationError("No updatable fields provided.")

        workspace_id = _workspace_id(request)
        acting_user = _acting_user(request)

        try:
            fd = SchemaRegistryService.update_field(
                workspace_id=workspace_id,
                entity_slug=slug,
                field_slug=field_slug,
                updates=updates,
                updated_by=acting_user,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        out = FieldDefinitionOutputSerializer(fd)
        return Response(out.data, status=status.HTTP_200_OK)

    def delete(self, request: Request, slug: str, field_slug: str) -> Response:
        workspace_id = _workspace_id(request)
        acting_user = _acting_user(request)

        try:
            SchemaRegistryService.remove_field(
                workspace_id=workspace_id,
                entity_slug=slug,
                field_slug=field_slug,
                updated_by=acting_user,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Schema Version views
# ---------------------------------------------------------------------------

class SchemaVersionListView(APIView):
    """
    GET /api/schema/entities/{slug}/versions/
      List all schema versions, newest first.
    """

    def get(self, request: Request, slug: str) -> Response:
        workspace_id = _workspace_id(request)

        try:
            versions = SchemaRegistryService.list_versions(
                workspace_id=workspace_id,
                entity_slug=slug,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        out = SchemaVersionOutputSerializer(versions, many=True)
        return Response(out.data, status=status.HTTP_200_OK)


class SchemaDiffView(APIView):
    """
    GET /api/schema/entities/{slug}/diff/?version_a=1&version_b=3
      Return a structural diff between two schema versions.
    """

    def get(self, request: Request, slug: str) -> Response:
        ser = DiffVersionsSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        workspace_id = _workspace_id(request)

        try:
            diff = SchemaRegistryService.diff_versions(
                workspace_id=workspace_id,
                entity_slug=slug,
                version_a=data["version_a"],
                version_b=data["version_b"],
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        return Response(diff, status=status.HTTP_200_OK)


class SchemaRollbackView(APIView):
    """
    POST /api/schema/entities/{slug}/rollback/
      Rollback entity field definitions to a previous schema version.

    Body: {"target_version": <int>}
    """

    def post(self, request: Request, slug: str) -> Response:
        ser = RollbackSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        workspace_id = _workspace_id(request)
        acting_user = _acting_user(request)

        try:
            entity = SchemaRegistryService.rollback_to_version(
                workspace_id=workspace_id,
                entity_slug=slug,
                target_version=data["target_version"],
                applied_by=acting_user,
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)

        out = EntityDefinitionOutputSerializer(entity)
        return Response(out.data, status=status.HTTP_200_OK)
