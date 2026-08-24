"""
Solution Document Service (Phase P2.6) — a reusable FRAMEWORK capability.

Numbered, audited "documents" recur in every solution (Procurement's PO/GR/VB, CRM's
Lead/Account/Opportunity, …). Rather than each domain re-implementing numbering + audit, this
service offers two generic, reusable operations on top of the existing engines:

  * ``create`` — allocate a gapless number (P2.1 Numbering) inside the record-write transaction
    and emit a creation event.
  * ``transition`` — update a record (status/stage change) and emit a lifecycle event.

Master data is read/written through ``RecordService`` so RBAC/ABAC/RLS apply. A domain's
"native" footprint shrinks to a small config + a couple of lifecycle calls — proving the
framework, not a custom app per domain, carries the weight.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import transaction

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.records.services import RecordService, resolve_entity


@dataclass
class SystemMember:
    """Minimal member the permissions layer understands (user_id/id/role/custom_role_id)."""
    user_id: uuid.UUID
    id: uuid.UUID
    role: str = "owner"
    custom_role_id = None


def system_member(actor_id):
    a = uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)
    return SystemMember(user_id=a, id=a)


def emit_event(workspace_id, aggregate_type, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type=aggregate_type).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type=aggregate_type, aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


class SolutionDocumentService:
    @staticmethod
    def create(*, workspace_id, entity_slug, data, member=None, actor_id=None,
               sequence_key=None, sequence_defaults=None, number_field="number",
               event_type=None):
        """Create a record; if ``sequence_key`` is given and ``number_field`` is empty, allocate
        a gapless number inside the same transaction (rollback rolls back the increment too)."""
        member = member or system_member(actor_id)
        entity = resolve_entity(workspace_id, entity_slug)
        payload = dict(data or {})
        with transaction.atomic():
            if sequence_key and not payload.get(number_field):
                from apps.numbering.services import NumberingService
                NumberingService.ensure_sequence(
                    workspace_id, sequence_key, defaults=sequence_defaults or {},
                    created_by=actor_id)
                payload[number_field] = NumberingService.allocate(
                    workspace_id, sequence_key, actor_id=actor_id,
                    context={"source_module": "solution", "source_ref": entity_slug})
            record = RecordService.create_record(
                workspace_id=workspace_id, member=member, entity=entity, data=payload)
        if event_type:
            emit_event(workspace_id, entity_slug, record["id"], event_type,
                       {"number": record.get(number_field), "entity": entity_slug}, actor_id)
        return record

    @staticmethod
    def transition(*, workspace_id, entity_slug, record_id, updates, member=None,
                   actor_id=None, event_type=None, event_payload=None):
        """Update a record (a status/stage change) and emit a lifecycle event."""
        member = member or system_member(actor_id)
        entity = resolve_entity(workspace_id, entity_slug)
        record = RecordService.update_record(
            workspace_id=workspace_id, member=member, entity=entity,
            record_id=record_id, data=updates)
        if event_type:
            payload = {"number": record.get("number")}
            payload.update(event_payload or {})
            emit_event(workspace_id, entity_slug, record_id, event_type, payload, actor_id)
        return record

    @staticmethod
    def retrieve(*, workspace_id, entity_slug, record_id, member=None, actor_id=None):
        member = member or system_member(actor_id)
        entity = resolve_entity(workspace_id, entity_slug)
        return RecordService.retrieve_record(
            workspace_id=workspace_id, member=member, entity=entity, record_id=record_id)
