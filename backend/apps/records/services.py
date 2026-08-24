"""
RecordService — the engine behind the auto-generated CRUD API.

Every operation: checks RBAC/ABAC (apps.permissions), reads via NQL (apps.nql),
writes to the physical table (apps.records.dal), emits a ``record.*`` domain event
(audited by the projection runner), and masks output fields. Workspace scoping +
soft-delete are enforced by NQL/DAL; PostgreSQL RLS is the DB backstop.
"""
from __future__ import annotations

import uuid

from django.db import transaction

from apps.computed.services import compute_fields
from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.nql.services import execute_nql
from apps.permissions import services as perm
from apps.permissions.services import PermissionError
from apps.rules.services import RuleBlocked, RuleEngine
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from . import dal


class RecordNotFound(Exception):  # noqa: N818 — domain "not found", not an error suffix
    pass


class EntityNotQueryable(Exception):  # noqa: N818 — domain condition, not an error suffix
    pass


def resolve_entity(workspace_id, slug):
    try:
        entity = SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=slug)
    except EntityNotFoundError as exc:
        raise EntityNotQueryable(str(exc)) from exc
    if not entity.has_physical_table or not entity.table_name:
        raise EntityNotQueryable(f"Entity {slug!r} has no physical table")
    return entity


def _emit(entity, event_type, record_id, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    rid = uuid.UUID(str(record_id))
    # Per-aggregate version (1,2,3…) so projectors can order/idempotently apply.
    version = DomainEvent.objects.filter(aggregate_id=rid).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=entity.workspace_id,
        aggregate_type="record", aggregate_id=rid, version=version,
        payload={"entity_slug": entity.slug, **payload},
        actor_id=actor_id or uuid.UUID(int=0)))


def _dispatch_workflow(entity, event_type, record_id, record_data, actor_id,
                       changed_fields=None):
    """Fire workflow triggers for a record event (post-commit, best-effort).

    Workflow dispatch must never break the originating record write, so failures
    here are swallowed — the event store remains the source of truth.
    """
    try:
        from apps.workflows.dispatcher import dispatch_record_event
        dispatch_record_event(
            event_type=event_type, entity_slug=entity.slug, entity_id=entity.id,
            record_id=record_id, record_data=record_data,
            workspace_id=entity.workspace_id, actor_id=actor_id,
            changed_fields=changed_fields)
    except Exception:  # noqa: BLE001 — automation must not break the write
        pass


def _attach_sla(entity, record_id, record_data):
    """Attach matching SLA policies to a new record (best-effort; never breaks the write)."""
    try:
        from apps.sla.services import SLAService
        SLAService.attach_policies(
            record_id=record_id, entity_slug=entity.slug, record_data=record_data,
            workspace_id=entity.workspace_id, entity_id=entity.id)
    except Exception:  # noqa: BLE001 — SLA attach must not break the write
        pass


def _recycle_on_delete(entity, record_id, record_view, actor_id):
    """Add a recycle-bin entry when a record is soft-deleted (best-effort)."""
    try:
        from apps.recyclebin.services import RecycleBinService
        title = next((str(record_view[k]) for k in ("name", "title", "label")
                      if record_view.get(k)), str(record_id))
        RecycleBinService.on_record_deleted(
            record_id=record_id, entity_id=entity.id, entity_slug=entity.slug,
            record_title=title, deleted_by=actor_id, workspace_id=entity.workspace_id)
    except Exception:  # noqa: BLE001 — recycle bin must not break the delete
        pass


def _recycle_on_restore(entity, record_id):
    """Drop the recycle-bin entry when a record is restored directly (best-effort)."""
    try:
        from apps.recyclebin.models import RecycleBinEntry
        RecycleBinEntry.objects.filter(
            workspace_id=entity.workspace_id, record_id=record_id, is_purged=False).delete()
    except Exception:  # noqa: BLE001
        pass


def _broadcast_realtime(entity, event_type, record_id, record_view, actor_id):
    """Push a live record patch to WebSocket subscribers (post-commit, best-effort)."""
    try:
        from apps.realtime.broadcast import broadcast_record
        broadcast_record(
            workspace_id=entity.workspace_id, entity_slug=entity.slug,
            event_type=event_type, record_id=record_id, data=record_view, actor_id=actor_id)
    except Exception:  # noqa: BLE001 — realtime fan-out must not break the write
        pass


def _reindex_search(entity, record_id):
    """Refresh the FTS index for a saved record (post-commit, best-effort).

    No-op on SQLite / when no SearchIndex exists; must never break the write.
    """
    def _run():
        try:
            from apps.search.services import SearchService
            SearchService.reindex_record(
                record_id=record_id, entity=entity, workspace_id=entity.workspace_id)
        except Exception:  # noqa: BLE001 — indexing must not break the write
            pass
    transaction.on_commit(_run)


def _allocate_auto_numbers(fmap, data, workspace_id) -> dict:
    """Allocate the next sequence value for each ``auto_number`` field not already
    provided. Gapless + concurrency-safe via a per-entity-field ``NumberSequence``
    (``SELECT ... FOR UPDATE``). The stored value is the integer; it is formatted with
    the field's prefix/padding on read (see ``dal.row_to_record``). Without this,
    auto_number columns stay NULL (e.g. an admission application never gets a number).
    """
    from apps.numbering.models import NumberSequence

    out: dict = {}
    for slug, fd in fmap.fields.items():
        if fd.field_type != "auto_number" or data.get(slug) not in (None, ""):
            continue
        cfg = fd.config or {}
        key = f"{fmap.entity.slug}__{slug}"[:100]
        with transaction.atomic():
            seq, _created = NumberSequence.objects.select_for_update().get_or_create(
                workspace_id=workspace_id, key=key,
                defaults={"name": f"{fmap.entity.slug} {slug}", "prefix": cfg.get("prefix", ""),
                          "suffix": cfg.get("suffix", ""), "padding": int(cfg.get("padding", 6) or 6),
                          "is_system": True})
            value = seq.start_value if not seq.initialized else seq.current_value + seq.increment
            seq.current_value = value
            seq.initialized = True
            seq.save(update_fields=["current_value", "initialized"])
        out[slug] = value
    return out


class RecordService:
    @staticmethod
    def list_records(*, workspace_id, member, entity, filter_source=None,
                     sort=None, limit=None, offset=None) -> list[dict]:
        perm.require(member, entity, "read")
        conds = []
        if filter_source:
            conds.append(filter_source)
        abac = perm.abac_list_conditions(member, entity, "read")
        if abac:
            conds.append(abac)
        query: dict = {"entity": entity.slug}
        if len(conds) == 1:
            query["filter"] = conds[0]
        elif len(conds) > 1:
            query["filter"] = {"op": "and", "conditions": conds}
        if sort:
            query["sort"] = sort
        if limit is not None:
            query["limit"] = limit
        if offset:
            query["offset"] = offset
        rows = execute_nql(workspace_id=workspace_id, source=query, user_id=member.user_id)
        fmap = dal.FieldMap(entity)
        records = [dal.row_to_record(r, fmap) for r in rows]
        return [perm.mask_record(member, entity, r) for r in records]

    @staticmethod
    def create_record(*, workspace_id, member, entity, data: dict) -> dict:
        perm.require(member, entity, "create")
        fmap = dal.FieldMap(entity)
        data = dict(data)
        data, blocked, _ = RuleEngine.apply(entity, data, "before_create", member)
        if blocked:
            raise RuleBlocked("Save blocked by a business rule.")
        data.update(compute_fields(entity, data))      # formula fields
        data.update(_allocate_auto_numbers(fmap, data, workspace_id))  # auto_number fields
        promoted, overflow = fmap.split(data, partial=False)
        with transaction.atomic():
            rid = dal.insert_row(entity, fmap, promoted, overflow, actor_id=member.user_id)
            _emit(entity, "record.created", rid, {"data": data}, member.user_id)
        written = dal.get_row(entity, fmap, rid)
        RuleEngine.apply(entity, {k: written.get(k) for k in fmap.fields},
                         "after_create", member, record_id=rid)
        record_view = {k: written.get(k) for k in fmap.fields}
        _dispatch_workflow(entity, "record_created", rid, record_view, member.user_id)
        _attach_sla(entity, rid, record_view)
        _reindex_search(entity, rid)
        _broadcast_realtime(entity, "record.created", rid, record_view, member.user_id)
        return perm.mask_record(member, entity, written)

    @staticmethod
    def retrieve_record(*, workspace_id, member, entity, record_id) -> dict:
        fmap = dal.FieldMap(entity)
        rec = dal.get_row(entity, fmap, record_id)
        if rec is None:
            raise RecordNotFound("Record not found")
        if not perm.check_record(member, entity, "read", rec):
            raise PermissionError("Not permitted to read this record")
        return perm.mask_record(member, entity, rec)

    @staticmethod
    def update_record(*, workspace_id, member, entity, record_id, data: dict) -> dict:
        fmap = dal.FieldMap(entity)
        rec = dal.get_row(entity, fmap, record_id)
        if rec is None:
            raise RecordNotFound("Record not found")
        if not perm.check_record(member, entity, "update", rec):
            raise PermissionError("Not permitted to update this record")
        for key in data:
            if key not in fmap.fields:
                from apps.nql.exceptions import UnknownFieldError
                raise UnknownFieldError(f"Unknown field {key!r}")
        field_view = {k: rec.get(k) for k in fmap.fields}
        field_view.update({k: v for k, v in data.items() if k in fmap.fields})
        field_view, blocked, _ = RuleEngine.apply(
            entity, field_view, "before_update", member, record_id=record_id)
        if blocked:
            raise RuleBlocked("Save blocked by a business rule.")
        field_view.update(compute_fields(entity, field_view))
        promoted, overflow = fmap.split(field_view, partial=True)
        with transaction.atomic():
            dal.update_row(entity, fmap, record_id, promoted, overflow, actor_id=member.user_id)
            _emit(entity, "record.updated", record_id, {"data": data}, member.user_id)
        updated = dal.get_row(entity, fmap, record_id)
        RuleEngine.apply(entity, {k: updated.get(k) for k in fmap.fields},
                         "after_update", member, record_id=record_id)
        record_view = {k: updated.get(k) for k in fmap.fields}
        changed = list(data.keys())
        _dispatch_workflow(entity, "record_updated", record_id, record_view,
                           member.user_id, changed_fields=changed)
        _dispatch_workflow(entity, "field_changed", record_id, record_view,
                           member.user_id, changed_fields=changed)
        _reindex_search(entity, record_id)
        _broadcast_realtime(entity, "record.updated", record_id, record_view, member.user_id)
        return perm.mask_record(member, entity, updated)

    @staticmethod
    def delete_record(*, workspace_id, member, entity, record_id) -> None:
        fmap = dal.FieldMap(entity)
        rec = dal.get_row(entity, fmap, record_id)
        if rec is None:
            raise RecordNotFound("Record not found")
        if not perm.check_record(member, entity, "delete", rec):
            raise PermissionError("Not permitted to delete this record")
        with transaction.atomic():
            dal.soft_delete_row(entity, record_id, actor_id=member.user_id)
            _emit(entity, "record.deleted", record_id, {}, member.user_id)
        record_view = {k: rec.get(k) for k in fmap.fields}
        _dispatch_workflow(entity, "record_deleted", record_id, record_view, member.user_id)
        _recycle_on_delete(entity, record_id, record_view, member.user_id)
        _broadcast_realtime(entity, "record.deleted", record_id, record_view, member.user_id)

    @staticmethod
    def restore_record(*, workspace_id, member, entity, record_id) -> dict:
        perm.require(member, entity, "restore")
        fmap = dal.FieldMap(entity)
        rec = dal.get_row(entity, fmap, record_id, include_deleted=True)
        if rec is None:
            raise RecordNotFound("Record not found")
        with transaction.atomic():
            dal.restore_row(entity, record_id)
            _emit(entity, "record.restored", record_id, {}, member.user_id)
        _recycle_on_restore(entity, record_id)
        restored = dal.get_row(entity, fmap, record_id)
        _broadcast_realtime(entity, "record.restored", record_id,
                            {k: restored.get(k) for k in fmap.fields}, member.user_id)
        return perm.mask_record(member, entity, restored)
