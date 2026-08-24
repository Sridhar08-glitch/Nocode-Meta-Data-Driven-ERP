"""
SchemaRegistryService
=====================
High-level service layer for the Nexus Schema Registry.

Responsibilities:
    * Create, retrieve and inspect ``EntityDefinition`` records
    * Add, remove and update ``FieldDefinition`` records
    * Trigger physical-table DDL via ``PhysicalTableGenerator``
    * Snapshot schema state into ``SchemaVersion`` after every mutation
    * Diff and rollback schema versions

All write operations are wrapped in a single ``transaction.atomic()`` so that
the metadata change and the DDL change either both succeed or both roll back.

Validation rules
----------------
    slug        Must match ``^[a-z][a-z0-9_]{0,62}$``
    field_type  Must be a value in ``FIELD_TYPE_VALUES``
    uniqueness  Entity slugs are unique per workspace; field slugs unique per entity

System field protection
-----------------------
Fields with ``is_system=True`` cannot be deleted and their immutable attributes
(slug, entity, workspace_id, is_system) cannot be changed via ``update_field``.

Error hierarchy
---------------
All public methods raise subclasses of ``SchemaRegistryError`` on logical
failures so callers can distinguish them from unexpected DB errors.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.metadata.models import (
    FIELD_TYPE_VALUES,
    EntityDefinition,
    FieldDefinition,
    SchemaVersion,
)
from apps.physical_tables.services import PhysicalTableGenerator
from apps.schema_registry.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    FieldAlreadyExistsError,
    FieldNotFoundError,
    InvalidFieldTypeError,
    InvalidSlugError,
    RollbackError,
    SchemaVersionNotFoundError,
    SystemFieldError,
)

# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')


def _validate_slug(slug: str, label: str = "slug") -> None:
    """Raise :class:`InvalidSlugError` if *slug* does not match the pattern."""
    if not _SLUG_RE.match(slug):
        raise InvalidSlugError(
            f"Invalid {label}: {slug!r}. Must start with a lowercase letter and "
            f"contain only lowercase letters, digits, or underscores (max 63 chars)."
        )


def _validate_field_type(field_type: str) -> None:
    """Raise :class:`InvalidFieldTypeError` if *field_type* is not recognised."""
    if field_type not in FIELD_TYPE_VALUES:
        raise InvalidFieldTypeError(
            f"Unknown field_type: {field_type!r}. Valid types: {sorted(FIELD_TYPE_VALUES)}"
        )


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _entity_snapshot(entity: EntityDefinition) -> dict[str, Any]:
    """Build a serialisable dict snapshot of *entity* and its current fields."""
    fields = []
    for fd in entity.fields.filter(is_deleted=False).order_by("order"):
        fields.append({
            "id": str(fd.pk),
            "slug": fd.slug,
            "name": fd.name,
            "field_type": fd.field_type,
            "description": fd.description,
            "is_promoted": fd.is_promoted,
            "column_name": fd.column_name,
            "is_filterable": fd.is_filterable,
            "is_sortable": fd.is_sortable,
            "is_searchable": fd.is_searchable,
            "has_index": fd.has_index,
            "is_required": fd.is_required,
            "is_unique": fd.is_unique,
            "default_value": fd.default_value,
            "is_system": fd.is_system,
            "is_hidden": fd.is_hidden,
            "is_readonly": fd.is_readonly,
            "order": fd.order,
            "config": fd.config,
            "read_roles": fd.read_roles,
            "write_roles": fd.write_roles,
        })
    return {
        "id": str(entity.pk),
        "workspace_id": str(entity.workspace_id),
        "slug": entity.slug,
        "name": entity.name,
        "plural_name": entity.plural_name,
        "description": entity.description,
        "table_name": entity.table_name,
        "has_physical_table": entity.has_physical_table,
        "current_schema_version": entity.current_schema_version,
        "title_field_slug": entity.title_field_slug,
        "settings": entity.settings,
        "fields": fields,
    }


def _snapshot_version(
    entity: EntityDefinition,
    *,
    version: int,
    migration_sql: str = "",
    applied_by: uuid.UUID | None = None,
) -> SchemaVersion:
    """Deactivate the current version, create a new one, and update the entity.

    Must be called inside an existing ``transaction.atomic()`` block.
    """
    SchemaVersion.objects.filter(entity=entity, is_current=True).update(is_current=False)

    sv = SchemaVersion.objects.create(
        entity=entity,
        workspace_id=entity.workspace_id,
        version=version,
        snapshot=_entity_snapshot(entity),
        migration_sql=migration_sql,
        applied_at=timezone.now(),
        applied_by=applied_by,
        is_current=True,
        parent_version=version - 1 if version > 1 else None,
    )

    entity.current_schema_version = version
    entity.save(update_fields=["current_schema_version"])
    return sv


def _emit(entity, event_type: str, payload: dict, actor_id: uuid.UUID | None) -> None:
    """Append a metadata change to the event store (audit/replay — §11).

    Called inside the mutation's transaction so the event and the schema change
    commit atomically. The audit projection consumes these into the audit trail.
    """
    from apps.eventstore.events import DomainEventData, DomainEventFactory

    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type,
        workspace_id=entity.workspace_id,
        aggregate_type="entity_definition",
        aggregate_id=entity.id,
        payload=payload,
        actor_id=actor_id or uuid.UUID(int=0),
        version=entity.current_schema_version,
    ))


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class SchemaRegistryService:
    """Stateless service class — all methods are classmethods."""

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    @classmethod
    def create_entity(
        cls,
        *,
        workspace_id: uuid.UUID,
        slug: str,
        name: str,
        plural_name: str,
        description: str = "",
        module_id=None,
        fields: list[dict[str, Any]] | None = None,
        settings: dict[str, Any] | None = None,
        title_field_slug: str = "name",
        created_by: uuid.UUID | None = None,
    ) -> EntityDefinition:
        """Create a new entity, its initial fields, and its physical DB table.

        A ``SchemaVersion`` with version=1 is snapshotted after the DDL.

        Raises:
            InvalidSlugError: if *slug* is malformed.
            EntityAlreadyExistsError: if *slug* already exists in the workspace.
            FieldAlreadyExistsError: if duplicate field slugs appear in *fields*.
        """
        _validate_slug(slug, "entity slug")

        if EntityDefinition.objects.filter(
            workspace_id=workspace_id, slug=slug
        ).exists():
            raise EntityAlreadyExistsError(
                f"Entity {slug!r} already exists in workspace {workspace_id}"
            )

        with transaction.atomic():
            entity = EntityDefinition.objects.create(
                workspace_id=workspace_id,
                slug=slug,
                name=name,
                plural_name=plural_name,
                description=description,
                module_id=module_id,
                table_name="",
                has_physical_table=False,
                current_schema_version=0,
                settings=settings or {},
                title_field_slug=title_field_slug,
            )

            if fields:
                seen_slugs: set = set()
                for order, fspec in enumerate(fields):
                    fslug = fspec.get("slug", "")
                    _validate_slug(fslug, f"field slug [{fslug!r}]")
                    if fslug in seen_slugs:
                        raise FieldAlreadyExistsError(
                            f"Duplicate field slug {fslug!r} in spec"
                        )
                    seen_slugs.add(fslug)
                    cls._create_field_definition(entity, fspec, order=order)

            PhysicalTableGenerator.create_table(entity)
            entity.refresh_from_db()

            _snapshot_version(
                entity,
                version=1,
                migration_sql="-- create_entity",
                applied_by=created_by,
            )
            _emit(entity, "entity.created",
                  {"slug": entity.slug, "name": entity.name}, created_by)

        return entity

    @classmethod
    def get_entity(
        cls,
        *,
        workspace_id: uuid.UUID,
        slug: str,
    ) -> EntityDefinition:
        """Return the entity or raise :class:`EntityNotFoundError`."""
        try:
            return EntityDefinition.objects.get(workspace_id=workspace_id, slug=slug)
        except EntityDefinition.DoesNotExist:
            raise EntityNotFoundError(
                f"Entity {slug!r} not found in workspace {workspace_id}"
            ) from None

    @classmethod
    def get_entity_schema(
        cls,
        *,
        workspace_id: uuid.UUID,
        slug: str,
    ) -> dict[str, Any]:
        """Return a full serialisable snapshot of the current entity schema."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=slug)
        return _entity_snapshot(entity)

    @classmethod
    def list_entities(cls, *, workspace_id: uuid.UUID, include_inactive: bool = False):
        """Return the workspace's entities (active only unless *include_inactive*)."""
        qs = EntityDefinition.objects.filter(workspace_id=workspace_id)
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs.order_by("name")

    @classmethod
    def soft_delete_entity(cls, *, workspace_id: uuid.UUID, slug: str,
                           deleted_by: uuid.UUID | None = None) -> EntityDefinition:
        """Deactivate an entity (``is_active=False``). The physical table is kept;
        hard deletion (DROP TABLE) is reserved for the admin API."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=slug)
        if entity.is_active:
            entity.is_active = False
            entity.updated_by = deleted_by
            entity.save(update_fields=["is_active", "updated_by"])
            _emit(entity, "entity.deleted", {"slug": entity.slug}, deleted_by)
        return entity

    @classmethod
    def update_entity(cls, *, workspace_id: uuid.UUID, slug: str,
                      updates: dict[str, Any], updated_by: uuid.UUID | None = None) -> EntityDefinition:
        """Update entity-level attributes (not schema — fields are separate)."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=slug)
        allowed = {"name", "plural_name", "description", "title_field_slug",
                   "settings", "is_active", "icon", "color"}
        changed = [k for k in updates if k in allowed]
        for key in changed:
            setattr(entity, key, updates[key])
        if changed:
            entity.updated_by = updated_by
            entity.save(update_fields=[*changed, "updated_by"])
            _emit(entity, "entity.updated", {"changed": changed}, updated_by)
        return entity

    # ------------------------------------------------------------------
    # Field operations
    # ------------------------------------------------------------------

    @classmethod
    def promote_field(cls, *, workspace_id: uuid.UUID, entity_slug: str,
                      field_slug: str, updated_by: uuid.UUID | None = None) -> FieldDefinition:
        """Promote a field to a real physical column (ADD COLUMN + version bump)."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        fd = cls._get_field(entity, field_slug)
        if fd.is_promoted:
            raise FieldAlreadyExistsError(f"Field {field_slug!r} is already promoted")
        return cls.update_field(
            workspace_id=workspace_id, entity_slug=entity_slug, field_slug=field_slug,
            updates={"is_promoted": True}, updated_by=updated_by,
        )

    @classmethod
    def demote_field(cls, *, workspace_id: uuid.UUID, entity_slug: str,
                     field_slug: str, updated_by: uuid.UUID | None = None) -> FieldDefinition:
        """Demote a promoted field back to JSON overflow (DROP COLUMN + version bump)."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        fd = cls._get_field(entity, field_slug)
        if not fd.is_promoted:
            raise FieldNotFoundError(f"Field {field_slug!r} is not promoted")
        return cls.update_field(
            workspace_id=workspace_id, entity_slug=entity_slug, field_slug=field_slug,
            updates={"is_promoted": False}, updated_by=updated_by,
        )

    @classmethod
    def add_field(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
        slug: str,
        name: str,
        field_type: str,
        description: str = "",
        is_promoted: bool = False,
        is_filterable: bool = True,
        is_sortable: bool = True,
        is_searchable: bool = False,
        has_index: bool = False,
        is_required: bool = False,
        is_unique: bool = False,
        default_value=None,
        config: dict[str, Any] | None = None,
        order: int = 0,
        read_roles: list[str] | None = None,
        write_roles: list[str] | None = None,
        updated_by: uuid.UUID | None = None,
    ) -> FieldDefinition:
        """Add a field to an existing entity.

        If ``is_promoted=True`` and the entity already has a physical table,
        the column is added immediately via DDL.

        A new ``SchemaVersion`` is snapshotted after every successful add.
        """
        _validate_slug(slug, "field slug")
        _validate_field_type(field_type)

        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)

        if FieldDefinition.objects.filter(entity=entity, slug=slug).exists():
            raise FieldAlreadyExistsError(
                f"Field {slug!r} already exists on entity {entity_slug!r}"
            )

        spec: dict[str, Any] = {
            "slug": slug,
            "name": name,
            "field_type": field_type,
            "description": description,
            "is_promoted": is_promoted,
            "is_filterable": is_filterable,
            "is_sortable": is_sortable,
            "is_searchable": is_searchable,
            "has_index": has_index,
            "is_required": is_required,
            "is_unique": is_unique,
            "default_value": default_value,
            "config": config or {},
            "order": order,
            "read_roles": read_roles or [],
            "write_roles": write_roles or [],
        }

        with transaction.atomic():
            fd = cls._create_field_definition(entity, spec, order=order)

            if is_promoted and entity.has_physical_table:
                PhysicalTableGenerator.add_column(entity, fd)
                fd.refresh_from_db()

            new_version = entity.current_schema_version + 1
            _snapshot_version(
                entity,
                version=new_version,
                migration_sql=f"-- add_field {slug}",
                applied_by=updated_by,
            )
            _emit(entity, "field.added", {"field_slug": slug, "field_type": field_type}, updated_by)

        return fd

    @classmethod
    def remove_field(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
        field_slug: str,
        updated_by: uuid.UUID | None = None,
    ) -> None:
        """Delete a non-system field from an entity.

        If the field is promoted, the column is dropped first.

        Raises:
            SystemFieldError: if the field is system-managed.
        """
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        fd = cls._get_field(entity, field_slug)

        if fd.is_system:
            raise SystemFieldError(
                f"Field {field_slug!r} is system-managed and cannot be removed"
            )

        with transaction.atomic():
            if fd.is_promoted and entity.has_physical_table:
                PhysicalTableGenerator.drop_column(entity, fd)

            fd.delete()

            new_version = entity.current_schema_version + 1
            _snapshot_version(
                entity,
                version=new_version,
                migration_sql=f"-- remove_field {field_slug}",
                applied_by=updated_by,
            )
            _emit(entity, "field.removed", {"field_slug": field_slug}, updated_by)

    @classmethod
    def soft_delete_field(
        cls, *, workspace_id: uuid.UUID, entity_slug: str, field_slug: str,
        updated_by: uuid.UUID | None = None,
    ) -> None:
        """Soft-delete a field (``is_deleted=True``) — never hard-drops data (§5.2).

        The physical column (if promoted) is **retained** so data is preserved and
        the field can be restored; the field is hidden from the schema/API. Hard
        deletion of a field with data is reserved for the admin purge path.
        """
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        fd = cls._get_field(entity, field_slug)
        if fd.is_system:
            raise SystemFieldError(
                f"Field {field_slug!r} is system-managed and cannot be deleted")
        with transaction.atomic():
            fd.is_deleted = True
            fd.save(update_fields=["is_deleted"])
            new_version = entity.current_schema_version + 1
            _snapshot_version(
                entity, version=new_version,
                migration_sql=f"-- soft_delete_field {field_slug}", applied_by=updated_by)
            _emit(entity, "field.deleted", {"field_slug": field_slug}, updated_by)

    @classmethod
    def update_field(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
        field_slug: str,
        updates: dict[str, Any],
        updated_by: uuid.UUID | None = None,
    ) -> FieldDefinition:
        """Apply *updates* to an existing field.

        Handles:
            * Promoting a non-promoted field → ADD COLUMN
            * Demoting a promoted field → DROP COLUMN
            * Changing field_type on a promoted field → ALTER TYPE (PG only)
            * Attribute-only changes (name, description, roles, …)

        Raises:
            SystemFieldError: if an immutable attribute is included in *updates*
                              for a system field.
            InvalidFieldTypeError: if ``field_type`` is being changed to an
                                   unknown value.
        """
        IMMUTABLE = {"slug", "entity", "workspace_id", "is_system"}

        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        fd = cls._get_field(entity, field_slug)

        if fd.is_system and set(updates.keys()) & IMMUTABLE:
            raise SystemFieldError(
                f"Cannot change immutable attributes on system field {field_slug!r}"
            )

        if "field_type" in updates:
            _validate_field_type(updates["field_type"])

        with transaction.atomic():
            new_field_type = updates.get("field_type", fd.field_type)
            new_config = updates.get("config", fd.config)

            # Determine DDL action before mutating fd
            promote_col = False
            demote_col = False
            type_changed = False

            if "is_promoted" in updates:
                if updates["is_promoted"] and not fd.is_promoted:
                    promote_col = True
                elif not updates["is_promoted"] and fd.is_promoted:
                    demote_col = True

            if "field_type" in updates and updates["field_type"] != fd.field_type:
                type_changed = True

            # Apply allowed attribute changes to the ORM instance
            allowed_keys = {
                "name", "description", "field_type", "is_promoted",
                "is_filterable", "is_sortable", "is_searchable", "has_index",
                "is_required", "is_unique", "default_value", "config",
                "order", "read_roles", "write_roles", "is_hidden", "is_readonly",
            }
            for key, value in updates.items():
                if key in allowed_keys:
                    setattr(fd, key, value)
            fd.save()

            # DDL (must happen after fd is saved so PhysicalTableGenerator
            # reads the new column_name / field_type from the DB)
            if entity.has_physical_table:
                if demote_col:
                    PhysicalTableGenerator.drop_column(entity, fd)
                    fd.refresh_from_db()
                elif promote_col:
                    PhysicalTableGenerator.add_column(entity, fd)
                    fd.refresh_from_db()
                elif type_changed and fd.is_promoted:
                    PhysicalTableGenerator.change_column_type(
                        entity, fd, new_field_type, new_config
                    )
                    fd.refresh_from_db()

            new_version = entity.current_schema_version + 1
            _snapshot_version(
                entity,
                version=new_version,
                migration_sql=f"-- update_field {field_slug}",
                applied_by=updated_by,
            )
            _emit(entity, "field.updated",
                  {"field_slug": field_slug, "changed": list(updates.keys())}, updated_by)

        return fd

    # ------------------------------------------------------------------
    # Version operations
    # ------------------------------------------------------------------

    @classmethod
    def list_versions(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
    ) -> list[SchemaVersion]:
        """Return all schema versions for *entity_slug* ordered newest first."""
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)
        return list(entity.schema_versions.order_by("-version"))

    @classmethod
    def diff_versions(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """Compare two schema versions.

        Returns a dict with keys:
            ``version_a``, ``version_b``
            ``added``   — fields present in B but not A
            ``removed`` — fields present in A but not B
            ``changed`` — fields present in both with attribute changes
        """
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)

        def _get_sv(v: int) -> SchemaVersion:
            try:
                return entity.schema_versions.get(version=v)
            except SchemaVersion.DoesNotExist:
                raise SchemaVersionNotFoundError(
                    f"Version {v} not found for entity {entity_slug!r}"
                ) from None

        sv_a = _get_sv(version_a)
        sv_b = _get_sv(version_b)

        fields_a = {f["slug"]: f for f in sv_a.snapshot.get("fields", [])}
        fields_b = {f["slug"]: f for f in sv_b.snapshot.get("fields", [])}

        added = [fields_b[s] for s in fields_b if s not in fields_a]
        removed = [fields_a[s] for s in fields_a if s not in fields_b]
        changed = []

        for slug in set(fields_a) & set(fields_b):
            fa, fb = fields_a[slug], fields_b[slug]
            diffs = {
                k: {"from": fa[k], "to": fb[k]}
                for k in fb
                if fa.get(k) != fb[k]
            }
            if diffs:
                changed.append({"slug": slug, "changes": diffs})

        return {
            "version_a": version_a,
            "version_b": version_b,
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    @classmethod
    def rollback_to_version(
        cls,
        *,
        workspace_id: uuid.UUID,
        entity_slug: str,
        target_version: int,
        applied_by: uuid.UUID | None = None,
    ) -> EntityDefinition:
        """Rebuild the entity's field set from a historical snapshot.

        Non-system fields are deleted and recreated from the snapshot.
        System fields that appear in the snapshot but do not already exist
        are recreated; existing system fields are left untouched.

        A new ``SchemaVersion`` is appended (version = current + 1) documenting
        the rollback. The physical table is **not** altered — only metadata
        is rolled back.

        Raises:
            SchemaVersionNotFoundError: if *target_version* does not exist.
            RollbackError: if the snapshot contains no field data.
        """
        entity = cls.get_entity(workspace_id=workspace_id, slug=entity_slug)

        try:
            sv = entity.schema_versions.get(version=target_version)
        except SchemaVersion.DoesNotExist:
            raise SchemaVersionNotFoundError(
                f"Version {target_version} not found for entity {entity_slug!r}"
            ) from None

        snapshot = sv.snapshot
        if "fields" not in snapshot:
            raise RollbackError(
                f"Snapshot for version {target_version} has no field data"
            )

        with transaction.atomic():
            # Delete all non-system fields
            entity.fields.filter(is_system=False).delete()

            # Recreate fields from snapshot
            for order, fspec in enumerate(snapshot["fields"]):
                if fspec.get("is_system"):
                    # System fields: only recreate if missing
                    if not entity.fields.filter(slug=fspec["slug"]).exists():
                        cls._create_field_definition(entity, fspec, order=order)
                    continue
                cls._create_field_definition(entity, fspec, order=order)

            # Delete schema versions beyond the target so we can reuse the
            # next sequential number.  e.g. rolling back to v1 deletes v2,
            # then the new rollback snapshot becomes v2 (target + 1).
            entity.schema_versions.filter(version__gt=target_version).delete()
            new_version = target_version + 1
            _snapshot_version(
                entity,
                version=new_version,
                migration_sql=f"-- rollback to version {target_version}",
                applied_by=applied_by,
            )

        return entity

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_field(entity: EntityDefinition, field_slug: str) -> FieldDefinition:
        """Return a field by slug or raise :class:`FieldNotFoundError`."""
        try:
            return entity.fields.get(slug=field_slug, is_deleted=False)
        except FieldDefinition.DoesNotExist:
            raise FieldNotFoundError(
                f"Field {field_slug!r} not found on entity {entity.slug!r}"
            ) from None

    @staticmethod
    def _create_field_definition(
        entity: EntityDefinition,
        spec: dict[str, Any],
        order: int = 0,
    ) -> FieldDefinition:
        """Create a ``FieldDefinition`` from a spec dict.

        Validates slug and field_type before creation.
        """
        slug = spec.get("slug", "")
        field_type = spec.get("field_type", "")
        _validate_slug(slug, f"field slug [{slug!r}]")
        _validate_field_type(field_type)

        return FieldDefinition.objects.create(
            entity=entity,
            workspace_id=entity.workspace_id,
            slug=slug,
            name=spec.get("name", slug),
            field_type=field_type,
            description=spec.get("description", ""),
            is_promoted=spec.get("is_promoted", False),
            column_name=spec.get("column_name", ""),
            is_filterable=spec.get("is_filterable", True),
            is_sortable=spec.get("is_sortable", True),
            is_searchable=spec.get("is_searchable", False),
            has_index=spec.get("has_index", False),
            is_required=spec.get("is_required", False),
            is_unique=spec.get("is_unique", False),
            default_value=spec.get("default_value"),
            config=spec.get("config") or {},
            order=spec.get("order", order),
            is_system=spec.get("is_system", False),
            is_hidden=spec.get("is_hidden", False),
            is_readonly=spec.get("is_readonly", False),
            read_roles=spec.get("read_roles") or [],
            write_roles=spec.get("write_roles") or [],
        )
