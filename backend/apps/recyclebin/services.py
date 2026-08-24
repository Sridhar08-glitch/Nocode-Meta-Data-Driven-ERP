"""
RecycleBinService (PROJECT_HANDBOOK.md §31.1).

Soft-deleted records are tracked here for a retention window, then hard-deleted by
the ``auto_purge`` beat. Restore clears ``deleted_at`` on the physical row (children
first); purge issues a real ``DELETE`` against the entity table. All actions emit
``record.*`` events.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import RecycleBinEntry

RETENTION_DAYS = getattr(settings, "NEXUS_RECYCLE_BIN_DAYS", 30)


class RecycleBinError(Exception):  # noqa: N818 — domain error
    pass


def _emit(workspace_id, record_id, event_type, payload, actor_id):
    # aggregate_type "recycle_bin" (not "record") so these events never pollute the
    # record event stream that rebuild_entity_records replays. record_id travels in
    # the payload for traceability.
    from apps.eventstore.models import DomainEvent
    rid = uuid.UUID(str(record_id))
    version = DomainEvent.objects.filter(
        aggregate_id=rid, aggregate_type="recycle_bin").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="recycle_bin", aggregate_id=rid, version=version,
        payload={"record_id": str(rid), **payload},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _system_member(actor_id):
    from apps.workflows.executors import SystemMember
    actor = actor_id or uuid.UUID(int=0)
    return SystemMember(user_id=actor, id=actor)


def _resolve_entity(workspace_id, slug):
    from apps.records.services import EntityNotQueryable, resolve_entity
    try:
        return resolve_entity(workspace_id, slug)
    except EntityNotQueryable:
        return None


class RecycleBinService:
    @staticmethod
    def on_record_deleted(*, record_id, entity_id, entity_slug, record_title="",
                          deleted_by=None, workspace_id, cascade_entries=None) -> RecycleBinEntry:
        from datetime import timedelta
        now = timezone.now()
        entry, _ = RecycleBinEntry.objects.update_or_create(
            workspace_id=workspace_id, record_id=record_id,
            defaults={"entity_id": entity_id, "entity_slug": entity_slug,
                      "record_title": (record_title or "")[:500], "deleted_by": deleted_by,
                      "deleted_at": now, "purge_after": now + timedelta(days=RETENTION_DAYS),
                      "cascade_entries": cascade_entries or [], "is_purged": False,
                      "purged_at": None})
        _emit(workspace_id, record_id, "record.moved_to_recycle_bin",
              {"entity_slug": entity_slug}, deleted_by)
        return entry

    @staticmethod
    def restore(entry_id, actor_id=None) -> uuid.UUID:
        from apps.records import dal
        entry = RecycleBinEntry.objects.filter(id=entry_id).first()
        if entry is None:
            raise RecycleBinError("Recycle bin entry not found")
        if entry.is_purged:
            raise RecycleBinError("Entry has been purged and cannot be restored")
        # restore cascade children first (reverse dependency order)
        for child in (entry.cascade_entries or []):
            child_entity = _resolve_entity(entry.workspace_id, child.get("entity_slug"))
            if child_entity is not None:
                dal.restore_row(child_entity, child.get("record_id"))
        entity = _resolve_entity(entry.workspace_id, entry.entity_slug)
        if entity is not None:
            dal.restore_row(entity, entry.record_id)
        _emit(entry.workspace_id, entry.record_id, "record.restored_from_recycle_bin",
              {"entity_slug": entry.entity_slug}, actor_id)
        entry.delete()
        return entry.record_id

    @staticmethod
    def purge_entry(entry_id, actor_id=None) -> None:
        entry = RecycleBinEntry.objects.filter(id=entry_id).first()
        if entry is None or entry.is_purged:
            return
        RecycleBinService._hard_delete(entry.workspace_id, entry.entity_slug, entry.record_id)
        for child in (entry.cascade_entries or []):
            RecycleBinService._hard_delete(entry.workspace_id, child.get("entity_slug"),
                                           child.get("record_id"))
        entry.is_purged = True
        entry.purged_at = timezone.now()
        entry.save(update_fields=["is_purged", "purged_at"])
        _emit(entry.workspace_id, entry.record_id, "record.permanently_deleted",
              {"entity_slug": entry.entity_slug}, actor_id)

    @staticmethod
    def _hard_delete(workspace_id, entity_slug, record_id) -> None:
        entity = _resolve_entity(workspace_id, entity_slug)
        if entity is None or not entity.table_name:
            return
        with connection.cursor() as cur:
            cur.execute(
                f'DELETE FROM "{entity.table_name}" WHERE id = %s AND workspace_id = %s',
                [str(record_id), str(workspace_id)])

    @staticmethod
    def purge_expired() -> int:
        now = timezone.now()
        expired = RecycleBinEntry.objects.filter(is_purged=False, purge_after__lte=now)
        count = 0
        for entry in expired.iterator(chunk_size=200):
            RecycleBinService.purge_entry(entry.id)
            count += 1
        return count

    @staticmethod
    def list_entries(workspace_id, *, include_purged=False):
        qs = RecycleBinEntry.objects.filter(workspace_id=workspace_id)
        if not include_purged:
            qs = qs.filter(is_purged=False)
        return qs.order_by("-deleted_at")
