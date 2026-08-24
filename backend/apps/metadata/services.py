"""
Form Schema service (Phase 1.26).

Serves the single canonical ``FormSchema`` the frontend Form Renderer consumes, and
backs the in-app Form Builder (authenticated ``FormDefinition`` CRUD). The schema is
resolved from ``FieldDefinition`` (+ an optional ``FormDefinition`` layout); when no
default form exists, a single-section layout is synthesised from the entity's fields.

Permission-aware: fields the caller cannot read (by ``read_roles``) are omitted, so the
schema never leaks hidden fields. Computed/system fields are marked read-only.
"""
from __future__ import annotations

import uuid

from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import FormDefinition

# Field types whose value is produced by the backend and must never be edited.
_READONLY_TYPES = {"formula", "rollup", "auto_number", "created_at", "updated_at",
                   "created_by", "updated_by"}
_ADMIN_ROLES = {"owner", "admin"}


class FormSchemaError(Exception):  # noqa: N818 — domain error
    pass


def _member_role(member) -> str:
    return getattr(member, "role", "") or ""


def _can_read_field(fd, member) -> bool:
    if _member_role(member) in _ADMIN_ROLES:
        return True
    roles = fd.read_roles or []
    return not roles or _member_role(member) in roles


def _field_payload(fd) -> dict:
    return {
        "slug": fd.slug,
        "name": fd.name,
        "field_type": fd.field_type,
        "description": fd.description,
        "is_required": fd.is_required,
        "is_unique": fd.is_unique,
        "is_hidden": fd.is_hidden,
        "is_readonly": fd.is_readonly or fd.field_type in _READONLY_TYPES,
        "is_system": fd.is_system,
        "default_value": fd.default_value,
        "validation_rules": fd.validation_rules or [],
        "config": fd.config or {},
        "order": fd.order,
        "read_roles": fd.read_roles or [],
        "write_roles": fd.write_roles or [],
    }


class FormSchemaService:
    @staticmethod
    def _entity(workspace_id, slug):
        try:
            return SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=slug)
        except EntityNotFoundError as exc:
            raise FormSchemaError(str(exc)) from exc

    @staticmethod
    def resolve_schema(*, workspace_id, entity_slug, member=None, form_id=None) -> dict:
        """Return the FormSchema for an entity (default form, a named form, or synthesised)."""
        entity = FormSchemaService._entity(workspace_id, entity_slug)
        fields = [fd for fd in entity.fields.filter(is_deleted=False).order_by("order", "created_at")
                  if _can_read_field(fd, member)]
        field_by_slug = {fd.slug: fd for fd in fields}

        form = None
        if form_id is not None:
            form = FormDefinition.objects.filter(
                id=form_id, workspace_id=workspace_id, entity=entity).first()
            if form is None:
                raise FormSchemaError("Form not found")
        if form is None:
            form = FormDefinition.objects.filter(
                workspace_id=workspace_id, entity=entity, is_default=True).first()

        settings = (form.settings if form else {}) or {}
        layout_type = settings.get("layout_type", "sections")
        conditional_rules = settings.get("conditional_rules", [])

        if form and form.layout:
            # Use the builder layout, but only reference fields the caller can read.
            sections = []
            used: set = set()
            for i, sec in enumerate(form.layout):
                slugs = [s for s in (sec.get("fields") or []) if s in field_by_slug]
                used.update(slugs)
                sections.append({
                    "key": sec.get("key") or sec.get("section") or f"section_{i}",
                    "title": sec.get("title", sec.get("section", "")),
                    "columns": int(sec.get("columns", 1)),
                    "fields": slugs,
                    "condition": sec.get("condition"),
                })
            # any readable field not placed in the layout is appended to a trailing section
            leftover = [fd.slug for fd in fields if fd.slug not in used]
            if leftover:
                sections.append({"key": "_more", "title": "", "columns": 1, "fields": leftover,
                                 "condition": None})
        else:
            # Synthesised default: one section with every readable field in order.
            sections = [{"key": "main", "title": "", "columns": 1,
                         "fields": [fd.slug for fd in fields], "condition": None}]

        return {
            "entity_slug": entity.slug,
            "entity_name": entity.name,
            "form_id": str(form.id) if form else None,
            "form_name": form.name if form else "Default",
            "layout_type": layout_type,
            "sections": sections,
            "fields": [_field_payload(field_by_slug[fd.slug]) for fd in fields],
            "conditional_rules": conditional_rules,
        }

    # ── Form Builder CRUD ──────────────────────────────────────────────────────
    @staticmethod
    def list_forms(*, workspace_id, entity_slug):
        entity = FormSchemaService._entity(workspace_id, entity_slug)
        return FormDefinition.objects.filter(
            workspace_id=workspace_id, entity=entity).order_by("-is_default", "name")

    @staticmethod
    def _valid_field_slugs(entity) -> set:
        return {fd.slug for fd in entity.fields.filter(is_deleted=False)}

    @staticmethod
    def _validate_layout(entity, layout):
        valid = FormSchemaService._valid_field_slugs(entity)
        for sec in layout or []:
            for slug in sec.get("fields", []) or []:
                if slug not in valid:
                    raise FormSchemaError(f"Layout references unknown field {slug!r}")

    @staticmethod
    def _validate_conditional_rules(entity, settings):
        """Every field referenced by a conditional rule must exist on the entity."""
        rules = (settings or {}).get("conditional_rules") or []
        if not isinstance(rules, list):
            raise FormSchemaError("conditional_rules must be a list")
        valid = FormSchemaService._valid_field_slugs(entity)
        for rule in rules:
            if not isinstance(rule, dict):
                raise FormSchemaError("each conditional rule must be an object")
            referenced = []
            for key in ("field", "target", "target_field"):
                if rule.get(key):
                    referenced.append(rule[key])
            for key in ("fields", "targets"):
                referenced.extend(rule.get(key) or [])
            for slug in referenced:
                if slug not in valid:
                    raise FormSchemaError(f"Conditional rule references unknown field {slug!r}")

    @staticmethod
    def create_form(*, workspace_id, entity_slug, data, created_by=None) -> FormDefinition:
        entity = FormSchemaService._entity(workspace_id, entity_slug)
        layout = data.get("layout") or []
        FormSchemaService._validate_layout(entity, layout)
        FormSchemaService._validate_conditional_rules(entity, data.get("settings") or {})
        is_default = bool(data.get("is_default"))
        form = FormDefinition.objects.create(
            workspace_id=workspace_id, entity=entity, name=data.get("name", "Form"),
            is_default=is_default, is_public=bool(data.get("is_public")),
            layout=layout, settings=data.get("settings") or {}, created_by=created_by)
        if is_default:
            FormDefinition.objects.filter(
                workspace_id=workspace_id, entity=entity, is_default=True).exclude(
                id=form.id).update(is_default=False)
        return form

    @staticmethod
    def update_form(*, workspace_id, entity_slug, form_id, data) -> FormDefinition:
        entity = FormSchemaService._entity(workspace_id, entity_slug)
        form = FormDefinition.objects.filter(
            id=form_id, workspace_id=workspace_id, entity=entity).first()
        if form is None:
            raise FormSchemaError("Form not found")
        if "layout" in data:
            FormSchemaService._validate_layout(entity, data["layout"])
            form.layout = data["layout"]
        if "settings" in data:
            FormSchemaService._validate_conditional_rules(entity, data["settings"] or {})
        for f in ("name", "is_public", "settings"):
            if f in data:
                setattr(form, f, data[f])
        if "is_default" in data:
            form.is_default = bool(data["is_default"])
        form.save()
        if form.is_default:
            FormDefinition.objects.filter(
                workspace_id=workspace_id, entity=entity, is_default=True).exclude(
                id=form.id).update(is_default=False)
        return form

    @staticmethod
    def delete_form(*, workspace_id, entity_slug, form_id) -> None:
        entity = FormSchemaService._entity(workspace_id, entity_slug)
        form = FormDefinition.objects.filter(
            id=form_id, workspace_id=workspace_id, entity=entity).first()
        if form is None:
            raise FormSchemaError("Form not found")
        form.delete()


def _as_uuid(value):
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
