"""
Declarative package migration runner.

A package upgrade may carry ordered, *additive-safe* migrations in its ``package.migrations``
list. Each migration is ``{"version": "1.1.0", "description": "...", "operations": [...]}`` and
runs exactly once per workspace (tracked on ``InstalledSolution.applied_migrations``). The
platform never executes package-authored code — operations are a fixed, validated vocabulary
applied through the existing engines (SchemaRegistry / appliers / parameterized SQL):

  add_entity      — create a new entity (+fields)         (idempotent; skips if present)
  add_field       — add a new field to an entity          (idempotent; never alters existing)
  set_default     — set a field's default value           (metadata only)
  deprecate_field — flag a field deprecated                (metadata only; never drops data)
  backfill        — set a constant on a field where empty  (via RecordService — the canonical
                                                            path; works for promoted columns and
                                                            custom_data alike, never raw SQL)
  add_role        — add a role (+permissions)              (reuses solution applier)
  add_report      — add a report                           (reuses marketplace applier)
  add_dashboard   — add a dashboard                        (reuses solution applier)
  add_workflow    — add a workflow                         (reuses marketplace applier)
  note            — no-op documentation step

No destructive operation exists (no drop/rename) — consistent with the platform's
data-safety rule that schema additions are never auto-removed.
"""
from __future__ import annotations

from django.db import transaction

from . import semver

_OP_REQUIRED = {
    "note": (),
    "add_entity": ("slug",),
    "add_field": ("entity", "field"),
    "set_default": ("entity", "field", "value"),
    "deprecate_field": ("entity", "field"),
    "backfill": ("entity", "field", "value"),
    "add_role": ("role",),
    "add_report": ("report",),
    "add_dashboard": ("dashboard",),
    "add_workflow": ("workflow",),
}


class MigrationError(Exception):  # noqa: N818 — domain error
    pass


# ── validation (pure) ─────────────────────────────────────────────────────────
def validate_migrations(migrations) -> list[str]:
    errors: list[str] = []
    if migrations in (None, []):
        return errors
    if not isinstance(migrations, list):
        return ["package.migrations must be a list"]
    seen = set()
    for i, mig in enumerate(migrations):
        if not isinstance(mig, dict):
            errors.append(f"package.migrations[{i}] must be an object")
            continue
        ver = mig.get("version")
        if not ver or not semver.is_valid(str(ver)):
            errors.append(f"package.migrations[{i}].version {ver!r} is not a valid version")
        elif ver in seen:
            errors.append(f"package.migrations duplicate version {ver!r}")
        else:
            seen.add(ver)
        ops = mig.get("operations")
        if not isinstance(ops, list):
            errors.append(f"package.migrations[{i}].operations must be a list")
            continue
        for j, op in enumerate(ops):
            if not isinstance(op, dict):
                errors.append(f"package.migrations[{i}].operations[{j}] must be an object")
                continue
            name = op.get("op")
            if name not in _OP_REQUIRED:
                errors.append(
                    f"package.migrations[{i}].operations[{j}] unknown op {name!r}")
                continue
            for key in _OP_REQUIRED[name]:
                if key not in op:
                    errors.append(
                        f"package.migrations[{i}].operations[{j}] ({name}) missing {key!r}")
    return errors


def pending_versions(migrations, from_version: str) -> list[dict]:
    """Migrations with version strictly greater than ``from_version``, ascending."""
    out = [m for m in (migrations or [])
           if semver.is_valid(str(m.get("version", ""))) and (
               not from_version or semver.compare(str(m["version"]), from_version) > 0)]
    return sorted(out, key=lambda m: semver.parse(str(m["version"])))


# ── execution ─────────────────────────────────────────────────────────────────
def _entity(workspace_id, slug):
    from apps.metadata.models import EntityDefinition
    return EntityDefinition.objects.filter(workspace_id=workspace_id, slug=slug).first()


def _field(workspace_id, entity, field_slug):
    from apps.metadata.models import FieldDefinition
    return FieldDefinition.objects.filter(
        workspace_id=workspace_id, entity_id=entity.id, slug=field_slug).first()


def _op_add_entity(op, workspace_id, actor_id):
    from apps.metadata.models import EntityDefinition
    from apps.schema_registry.services import SchemaRegistryService
    slug = op["slug"]
    if EntityDefinition.objects.filter(workspace_id=workspace_id, slug=slug).exists():
        return
    SchemaRegistryService.create_entity(
        workspace_id=workspace_id, slug=slug, name=op.get("name", slug),
        plural_name=op.get("plural_name", op.get("name", slug)),
        description=op.get("description", ""), fields=op.get("fields", []) or [],
        created_by=actor_id)


def _op_add_field(op, workspace_id, actor_id):
    from apps.schema_registry.services import SchemaRegistryService
    entity = _entity(workspace_id, op["entity"])
    if entity is None:
        raise MigrationError(f"add_field: entity {op['entity']!r} not found")
    fd = op["field"]
    if _field(workspace_id, entity, fd["slug"]) is not None:
        return  # never alter an existing field
    SchemaRegistryService.add_field(
        workspace_id=workspace_id, entity_slug=op["entity"], slug=fd["slug"],
        name=fd.get("name", fd["slug"]), field_type=fd["field_type"],
        description=fd.get("description", ""), is_promoted=fd.get("is_promoted", False),
        is_required=fd.get("is_required", False), is_unique=fd.get("is_unique", False),
        is_filterable=fd.get("is_filterable", True), is_sortable=fd.get("is_sortable", True),
        config=fd.get("config"), updated_by=actor_id)


def _op_set_default(op, workspace_id, actor_id):
    entity = _entity(workspace_id, op["entity"])
    if entity is None:
        raise MigrationError(f"set_default: entity {op['entity']!r} not found")
    fd = _field(workspace_id, entity, op["field"])
    if fd is None:
        raise MigrationError(f"set_default: field {op['field']!r} not found")
    cfg = dict(fd.config or {})
    cfg["default_value"] = op["value"]
    fd.config = cfg
    fd.save(update_fields=["config"])


def _op_deprecate_field(op, workspace_id, actor_id):
    entity = _entity(workspace_id, op["entity"])
    if entity is None:
        raise MigrationError(f"deprecate_field: entity {op['entity']!r} not found")
    fd = _field(workspace_id, entity, op["field"])
    if fd is None:
        raise MigrationError(f"deprecate_field: field {op['field']!r} not found")
    cfg = dict(fd.config or {})
    cfg["deprecated"] = True
    fd.config = cfg
    fd.save(update_fields=["config"])


def _op_backfill(op, workspace_id, actor_id):
    """Set a constant on a field for every record where it is currently empty — through
    ``RecordService`` (the canonical write path, so it works for promoted columns AND
    custom_data, applies rules/RLS, and never touches raw SQL). Bounded by the NQL max-limit
    like any list query."""
    from apps.records.services import RecordService
    from apps.solution_templates.documents import system_member

    entity = _entity(workspace_id, op["entity"])
    if entity is None:
        raise MigrationError(f"backfill: entity {op['entity']!r} not found")
    if _field(workspace_id, entity, op["field"]) is None:
        raise MigrationError(f"backfill: field {op['field']!r} not found")

    field_slug, value = op["field"], op["value"]
    member = system_member(actor_id)
    for rec in RecordService.list_records(
            workspace_id=workspace_id, member=member, entity=entity):
        if not rec.get(field_slug):
            RecordService.update_record(
                workspace_id=workspace_id, member=member, entity=entity,
                record_id=rec["id"], data={field_slug: value})


def _mini_manifest(key, item):
    return {key: [item]}


def _op_add_role(op, workspace_id, actor_id):
    from apps.solution_templates import appliers
    appliers.apply_roles(_mini_manifest("roles", op["role"]), workspace_id)


def _op_add_dashboard(op, workspace_id, actor_id):
    from apps.solution_templates import appliers
    appliers.apply_dashboards(_mini_manifest("dashboards", op["dashboard"]), workspace_id)


def _op_add_report(op, workspace_id, actor_id):
    from apps.marketplace import services as mk
    mk._apply_reports(_mini_manifest("reports", op["report"]), workspace_id)


def _op_add_workflow(op, workspace_id, actor_id):
    from apps.marketplace import services as mk
    mk._apply_workflows(_mini_manifest("workflows", op["workflow"]), workspace_id)


_DISPATCH = {
    "note": lambda *a: None,
    "add_entity": _op_add_entity,
    "add_field": _op_add_field,
    "set_default": _op_set_default,
    "deprecate_field": _op_deprecate_field,
    "backfill": _op_backfill,
    "add_role": _op_add_role,
    "add_dashboard": _op_add_dashboard,
    "add_report": _op_add_report,
    "add_workflow": _op_add_workflow,
}


def run_migration(migration: dict, *, workspace_id, actor_id=None) -> None:
    """Apply one migration's operations atomically."""
    with transaction.atomic():
        for op in migration.get("operations", []) or []:
            handler = _DISPATCH.get(op.get("op"))
            if handler is None:
                raise MigrationError(f"unknown migration op {op.get('op')!r}")
            handler(op, workspace_id, actor_id)


def run_pending(migrations, *, workspace_id, from_version, actor_id=None,
                already_applied=None) -> list[str]:
    """Run every migration newer than ``from_version`` (and not already applied), ascending.
    Returns the list of versions applied (as strings)."""
    applied_set = set(already_applied or [])
    applied: list[str] = []
    for mig in pending_versions(migrations, from_version):
        ver = str(mig["version"])
        if ver in applied_set:
            continue
        run_migration(mig, workspace_id=workspace_id, actor_id=actor_id)
        applied.append(ver)
    return applied
