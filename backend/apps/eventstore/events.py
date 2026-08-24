"""
Domain event value objects and the DomainEventFactory.

DomainEvent *model* lives in apps/eventstore/models.py.
This module defines:
  - DomainEventData  — in-memory value object passed between layers
  - DomainEventFactory — creates and persists DomainEvent model instances
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from django.db import transaction

# ── In-memory event value object ────────────────────────────────────────────

@dataclass(frozen=True)
class DomainEventData:
    """
    Immutable value object representing a domain event before/after persistence.

    Handlers return a list of these; the command bus persists them.

    Field notes:
      - version: the aggregate's version number AFTER this event is applied.
        Used for optimistic concurrency.  Defaults to 1.
      - event_version: schema version of this event *type* (for upcasting old events).
        Defaults to 1.  Increment when the event payload shape changes.
    """
    event_type: str                         # e.g. "record.created"
    workspace_id: uuid.UUID
    aggregate_type: str                     # e.g. "Record", "WorkflowRun"
    aggregate_id: uuid.UUID
    payload: dict[str, Any]                 # domain-specific data
    actor_id: uuid.UUID                     # who triggered the event
    version: int = 1                        # aggregate version AFTER this event
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    causation_id: uuid.UUID | None = None   # command correlation_id that caused this
    event_version: int = 1                  # schema version of this event type (upcasting)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "workspace_id": str(self.workspace_id),
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "payload": self.payload,
            "actor_id": str(self.actor_id),
            "version": self.version,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
        }


# ── DomainEventFactory ───────────────────────────────────────────────────────

class DomainEventFactory:
    """
    Persists DomainEventData value objects as DomainEvent model rows.

    This is the ONLY place that calls DomainEvent(...).save().
    All callers go through here so we enforce:
      - Workspace RLS context (SET LOCAL app.workspace_id)
      - Immutability check (DomainEvent.save raises on update)
      - Atomic batch insert
    """

    @staticmethod
    def persist_batch(
        events: list[DomainEventData],
        *,
        set_rls_context: bool = True,
    ) -> list[DomainEvent]:  # noqa: F821 — forward ref resolved at runtime
        """
        Persist a list of DomainEventData objects in a single transaction.

        Must be called inside an existing transaction (command bus wraps this).
        Returns the saved model instances.
        """
        from apps.eventstore.models import DomainEvent  # local import avoids circulars
        from apps.eventstore.rls import set_workspace_rls

        if not events:
            return []

        # Validate all events share the same workspace (they must).
        workspace_ids = {str(e.workspace_id) for e in events}
        if len(workspace_ids) > 1:
            raise ValueError(
                f"Cannot persist events from multiple workspaces in one batch: {workspace_ids}"
            )

        workspace_id = events[0].workspace_id

        saved: list[DomainEvent] = []
        with transaction.atomic():
            if set_rls_context:
                set_workspace_rls(str(workspace_id))

            for event_data in events:
                instance = DomainEvent(
                    event_type=event_data.event_type,
                    workspace_id=event_data.workspace_id,
                    aggregate_type=event_data.aggregate_type,
                    aggregate_id=event_data.aggregate_id,
                    version=event_data.version,
                    event_version=event_data.event_version,
                    payload=event_data.payload,
                    actor_id=event_data.actor_id,
                    correlation_id=event_data.correlation_id,
                    causation_id=event_data.causation_id,
                    occurred_at=event_data.occurred_at,
                )
                instance.save()   # DomainEvent.save() raises if pk already set
                saved.append(instance)

        return saved

    @staticmethod
    def persist_one(event_data: DomainEventData, *, set_rls_context: bool = True) -> DomainEvent:  # noqa: F821
        """Convenience wrapper for a single event."""
        results = DomainEventFactory.persist_batch([event_data], set_rls_context=set_rls_context)
        return results[0]
