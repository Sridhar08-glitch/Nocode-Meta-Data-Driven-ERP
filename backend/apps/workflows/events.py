"""
Domain-event emission for the workflow engine.

Each ``WorkflowRun`` is an event-sourced aggregate (``aggregate_type="workflow_run"``);
``workflow.*`` events are appended in per-run version order so the activity feed
(Phase 1.14) and audit trail can replay them. This is the only place the workflow
engine writes to the event store.
"""
from __future__ import annotations

import uuid

from apps.eventstore.events import DomainEventData, DomainEventFactory


def emit_workflow_event(*, event_type: str, workspace_id, run_id, payload: dict,
                        actor_id=None) -> None:
    """Append a ``workflow.*`` event for the given run (aggregate)."""
    from apps.eventstore.models import DomainEvent

    rid = uuid.UUID(str(run_id))
    version = DomainEvent.objects.filter(aggregate_id=rid).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type,
        workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="workflow_run",
        aggregate_id=rid,
        version=version,
        payload=payload or {},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0),
    ))
    # Live workflow-run status fan-out to WebSocket subscribers (best-effort).
    if event_type.startswith("workflow.run."):
        try:
            from apps.realtime.broadcast import broadcast_workflow
            broadcast_workflow(
                workspace_id=workspace_id, event_type=event_type, run_id=rid,
                definition_id=(payload or {}).get("workflow_id"),
                status=(payload or {}).get("status"), actor_id=actor_id)
        except Exception:  # noqa: BLE001 — realtime fan-out must not break the run
            pass
