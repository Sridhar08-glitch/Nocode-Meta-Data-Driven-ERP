"""
Metadata CRUD API (Phase 1.7) — public, production-facing endpoints under
``/api/v1/metadata/``.

Workspace scoping comes from ``request.workspace_id`` set by ``TenantMiddleware``
(after membership verification + RLS activation). All schema logic is delegated to
the existing ``SchemaRegistryService`` — no duplicate engine.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schema_registry.exceptions import SchemaRegistryError
from apps.schema_registry.serializers import (
    AddFieldSerializer,
    CreateEntitySerializer,
    EntityDefinitionOutputSerializer,
    FieldDefinitionOutputSerializer,
    SchemaVersionOutputSerializer,
    UpdateFieldSerializer,
)
from apps.schema_registry.services import SchemaRegistryService
from apps.schema_registry.views import _map_exception  # reuse domain→HTTP mapping

from . import impact
from .models import FieldDefinition, Module
from .serializers import (
    EntityUpdateSerializer,
    FieldSlugSerializer,
    FormCreateSerializer,
    FormDefinitionOutputSerializer,
    FormUpdateSerializer,
    ModuleSerializer,
)
from .services import FormSchemaError, FormSchemaService

_BUILDER_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _uid(request):
    return getattr(request.user, "id", None)


def _member(request):
    return getattr(request, "workspace_member", None)


def _require_builder(request):
    member = _member(request)
    if member is None or getattr(member, "role", "") not in _BUILDER_ROLES:
        raise PermissionDenied("Form builder requires an admin or owner role.")


# ── Modules (sidebar grouping) ────────────────────────────────────────────────
class ModuleListCreateView(APIView):
    def get(self, request):
        qs = Module.objects.filter(workspace_id=_ws(request))
        if request.query_params.get("include_inactive") not in ("1", "true", "True"):
            qs = qs.filter(is_active=True)
        return Response(ModuleSerializer(qs.order_by("order", "name"), many=True).data)

    def post(self, request):
        _require_builder(request)
        ser = ModuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if Module.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A module with this slug already exists.")
        module = ser.save(workspace_id=ws)
        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)


class ModuleDetailView(APIView):
    def _get(self, request, module_id):
        m = Module.objects.filter(workspace_id=_ws(request), id=module_id).first()
        if m is None:
            raise ValidationError("Module not found.")
        return m

    def get(self, request, module_id):
        return Response(ModuleSerializer(self._get(request, module_id)).data)

    def patch(self, request, module_id):
        _require_builder(request)
        module = self._get(request, module_id)
        ser = ModuleSerializer(module, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ModuleSerializer(module).data)

    def delete(self, request, module_id):
        _require_builder(request)
        self._get(request, module_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Entities ────────────────────────────────────────────────────────────────
class EntityListCreateView(APIView):
    def get(self, request):
        include_inactive = request.query_params.get("include_inactive") in ("1", "true", "True")
        entities = SchemaRegistryService.list_entities(
            workspace_id=_ws(request), include_inactive=include_inactive)
        data = EntityDefinitionOutputSerializer(entities, many=True).data
        # Annotate per-member RBAC so the metadata-driven sidebar can hide unreadable
        # entities (builders ignore the flags; the record API still enforces RBAC/ABAC).
        member = _member(request)
        if member is not None:
            from apps.permissions import services as perm
            by_id = {str(e.id): e for e in entities}
            for row in data:
                ent = by_id[str(row["id"])]
                row["can_read"] = perm.check(member, ent, "read")
                row["can_create"] = perm.check(member, ent, "create")
        return Response(data)

    def post(self, request):
        ser = CreateEntitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            entity = SchemaRegistryService.create_entity(
                workspace_id=_ws(request),
                slug=data["slug"], name=data["name"], plural_name=data["plural_name"],
                description=data.get("description", ""),
                fields=data.get("fields") or [],
                settings=data.get("settings") or {},
                title_field_slug=data.get("title_field_slug", "name"),
                created_by=_uid(request),
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(EntityDefinitionOutputSerializer(entity).data, status=status.HTTP_201_CREATED)


class EntityDetailView(APIView):
    def get(self, request, slug):
        try:
            schema = SchemaRegistryService.get_entity_schema(workspace_id=_ws(request), slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(schema)

    def patch(self, request, slug):
        ser = EntityUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data:
            raise ValidationError("No updatable fields provided.")
        try:
            entity = SchemaRegistryService.update_entity(
                workspace_id=_ws(request), slug=slug,
                updates=ser.validated_data, updated_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(EntityDefinitionOutputSerializer(entity).data)

    def delete(self, request, slug):
        try:
            SchemaRegistryService.soft_delete_entity(
                workspace_id=_ws(request), slug=slug, deleted_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Fields ──────────────────────────────────────────────────────────────────
class FieldListCreateView(APIView):
    def get(self, request, slug):
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=_ws(request), slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        fields = entity.fields.filter(is_deleted=False).order_by("order")
        return Response(FieldDefinitionOutputSerializer(fields, many=True).data)

    def post(self, request, slug):
        ser = AddFieldSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            fd = SchemaRegistryService.add_field(
                workspace_id=_ws(request), entity_slug=slug,
                slug=d["slug"], name=d["name"], field_type=d["field_type"],
                description=d.get("description", ""),
                is_promoted=d.get("is_promoted", False),
                is_filterable=d.get("is_filterable", True),
                is_sortable=d.get("is_sortable", True),
                is_searchable=d.get("is_searchable", False),
                has_index=d.get("has_index", False),
                is_required=d.get("is_required", False),
                is_unique=d.get("is_unique", False),
                default_value=d.get("default_value"),
                config=d.get("config") or {},
                order=d.get("order", 0),
                read_roles=d.get("read_roles") or [],
                write_roles=d.get("write_roles") or [],
                updated_by=_uid(request),
            )
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(FieldDefinitionOutputSerializer(fd).data, status=status.HTTP_201_CREATED)


class FieldDetailView(APIView):
    def get(self, request, slug, field_slug):
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=_ws(request), slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        fd = entity.fields.filter(slug=field_slug, is_deleted=False).first()
        if fd is None:
            raise ValidationError(f"Field {field_slug!r} not found.")
        return Response(FieldDefinitionOutputSerializer(fd).data)

    def patch(self, request, slug, field_slug):
        ser = UpdateFieldSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data:
            raise ValidationError("No updatable fields provided.")
        try:
            fd = SchemaRegistryService.update_field(
                workspace_id=_ws(request), entity_slug=slug, field_slug=field_slug,
                updates=ser.validated_data, updated_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(FieldDefinitionOutputSerializer(fd).data)

    def delete(self, request, slug, field_slug):
        # Soft-delete (§5.2): the field is hidden and data preserved, never hard-dropped.
        try:
            SchemaRegistryService.soft_delete_field(
                workspace_id=_ws(request), entity_slug=slug, field_slug=field_slug,
                updated_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Promote / demote ────────────────────────────────────────────────────────
class PromoteFieldView(APIView):
    def post(self, request, slug):
        ser = FieldSlugSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            fd = SchemaRegistryService.promote_field(
                workspace_id=_ws(request), entity_slug=slug,
                field_slug=ser.validated_data["field_slug"], updated_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(FieldDefinitionOutputSerializer(fd).data)


class DemoteFieldView(APIView):
    def post(self, request, slug):
        ser = FieldSlugSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            fd = SchemaRegistryService.demote_field(
                workspace_id=_ws(request), entity_slug=slug,
                field_slug=ser.validated_data["field_slug"], updated_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(FieldDefinitionOutputSerializer(fd).data)


# ── Schema versions ─────────────────────────────────────────────────────────
class SchemaVersionListView(APIView):
    def get(self, request, slug):
        try:
            versions = SchemaRegistryService.list_versions(workspace_id=_ws(request), entity_slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(SchemaVersionOutputSerializer(versions, many=True).data)


class SchemaRollbackView(APIView):
    def post(self, request, slug, version):
        try:
            entity = SchemaRegistryService.rollback_to_version(
                workspace_id=_ws(request), entity_slug=slug,
                target_version=int(version), applied_by=_uid(request))
        except SchemaRegistryError as exc:
            _map_exception(exc)
        return Response(EntityDefinitionOutputSerializer(entity).data)


# ── Form Schema + Form Builder (Phase 1.26) ──────────────────────────────────
class FormSchemaView(APIView):
    """Resolved canonical FormSchema the frontend Form Renderer consumes."""

    def get(self, request, slug):
        form_id = request.query_params.get("form_id")
        try:
            schema = FormSchemaService.resolve_schema(
                workspace_id=_ws(request), entity_slug=slug,
                member=_member(request), form_id=form_id or None)
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(schema)


class FormListCreateView(APIView):
    def get(self, request, slug):
        try:
            forms = FormSchemaService.list_forms(workspace_id=_ws(request), entity_slug=slug)
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(FormDefinitionOutputSerializer(forms, many=True).data)

    def post(self, request, slug):
        _require_builder(request)
        ser = FormCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            form = FormSchemaService.create_form(
                workspace_id=_ws(request), entity_slug=slug,
                data=ser.validated_data, created_by=_uid(request))
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(FormDefinitionOutputSerializer(form).data, status=status.HTTP_201_CREATED)


class FormDetailView(APIView):
    def get(self, request, slug, form_id):
        try:
            form = FormSchemaService.list_forms(
                workspace_id=_ws(request), entity_slug=slug).filter(id=form_id).first()
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        if form is None:
            raise ValidationError("Form not found")
        return Response(FormDefinitionOutputSerializer(form).data)

    def patch(self, request, slug, form_id):
        _require_builder(request)
        ser = FormUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data:
            raise ValidationError("No updatable fields provided.")
        try:
            form = FormSchemaService.update_form(
                workspace_id=_ws(request), entity_slug=slug,
                form_id=form_id, data=ser.validated_data)
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(FormDefinitionOutputSerializer(form).data)

    def delete(self, request, slug, form_id):
        _require_builder(request)
        try:
            FormSchemaService.delete_form(
                workspace_id=_ws(request), entity_slug=slug, form_id=form_id)
        except FormSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Impact analysis (Phase P1.4): what references this entity / field? ──────────
class EntityImpactView(APIView):
    """GET /entities/{slug}/impact/ — config objects that depend on this entity."""

    def get(self, request, slug):
        _member(request)
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=_ws(request), slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        deps = impact.entity_impact(_ws(request), entity)
        return Response({"entity_slug": slug, "dependents": deps, "count": len(deps)})


class FieldImpactView(APIView):
    """GET /entities/{slug}/fields/{field_slug}/impact/ — config objects that use this field."""

    def get(self, request, slug, field_slug):
        _member(request)
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=_ws(request), slug=slug)
        except SchemaRegistryError as exc:
            _map_exception(exc)
        field = FieldDefinition.objects.filter(entity_id=entity.id, slug=field_slug).first()
        if field is None:
            raise NotFound("Field not found.")
        deps = impact.field_impact(_ws(request), entity, field)
        return Response({"entity_slug": slug, "field_slug": field_slug, "dependents": deps, "count": len(deps)})
