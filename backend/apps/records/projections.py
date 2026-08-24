"""
Record read-model projectors (Pillar 2 / §5.2A).

These make the physical entity tables genuine **projections of the event stream**:
``record.*`` domain events are applied to the table idempotently (keyed on the
row's ``_event_version``), so a table can be truncated and rebuilt purely by
replaying its events — the foundation for replay, time-travel, and PITR.

On the live write path the row is written directly (CQRS-lite); these projectors
own the *rebuild* path (``rebuild_entity_records``) and double as a safety net.
"""
from __future__ import annotations

import logging

from django.db import connection

from apps.eventstore.models import DomainEvent
from apps.eventstore.projectors import event_projector, get_projectors
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from . import dal

logger = logging.getLogger(__name__)


def _resolve(event):
    slug = (event.payload or {}).get("entity_slug")
    if not slug:
        return None
    try:
        entity = SchemaRegistryService.get_entity(workspace_id=event.workspace_id, slug=slug)
    except EntityNotFoundError:
        return None
    return entity if entity.table_name else None


@event_projector("record.created", "record.updated")
def project_record_upsert(event) -> None:
    entity = _resolve(event)
    if entity is None:
        return
    fmap = dal.FieldMap(entity)
    rid = str(event.aggregate_id)
    current = dal.get_event_version(entity, rid)
    if current is not None and current >= event.version:
        return  # already applied — idempotent
    data = (event.payload or {}).get("data", {}) or {}
    promoted, overflow = fmap.split(data, partial=True)
    if current is None:
        dal.insert_row(entity, fmap, promoted, overflow, actor_id=event.actor_id,
                       record_id=rid, event_version=event.version)
    else:
        dal.update_row(entity, fmap, rid, promoted, overflow,
                       actor_id=event.actor_id, event_version=event.version)


@event_projector("record.deleted", "record.restored")
def project_record_delete(event) -> None:
    entity = _resolve(event)
    if entity is None:
        return
    rid = str(event.aggregate_id)
    current = dal.get_event_version(entity, rid)
    if current is not None and current >= event.version:
        return
    dal.set_deleted(entity, rid, deleted=(event.event_type == "record.deleted"),
                    event_version=event.version, actor_id=event.actor_id)


def rebuild_entity_records(entity) -> int:
    """Truncate the entity's physical table and rebuild every row from its
    ``record.*`` events (in global_sequence order). Returns the event count replayed."""
    with connection.cursor() as cur:
        cur.execute(f'DELETE FROM "{entity.table_name}"')
    events = (
        DomainEvent.objects
        .filter(workspace_id=entity.workspace_id, aggregate_type="record",
                payload__entity_slug=entity.slug)
        .order_by("global_sequence")
    )
    count = 0
    for event in events:
        for projector in get_projectors(event.event_type):
            projector(event)
        count += 1
    return count
