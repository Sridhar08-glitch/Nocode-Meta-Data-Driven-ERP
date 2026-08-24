"""
Projection runner — replays persisted DomainEvents into read models (Pillar 2).

Reads events after a per-projection checkpoint in ``global_sequence`` order and
dispatches each to the registered projectors (type-specific + wildcard ``"*"``),
advancing the checkpoint. Projectors are idempotent, so re-runs and full rebuilds
are safe.

This is the runtime that makes "read models are projections of the event stream"
real. Record read-models (physical tables) plug in here once the records runtime
(Phase 1.9) registers their projectors; today the audit trail is the live consumer.
"""
import logging

from apps.eventstore.models import DomainEvent, ProjectionCheckpoint
from apps.eventstore.projectors import get_projectors

logger = logging.getLogger(__name__)

DEFAULT_PROJECTION = "default"


def run_projections(*, projection_name: str = DEFAULT_PROJECTION, batch_size: int = 1000) -> int:
    """Dispatch all events after the checkpoint to their projectors.

    Returns the number of events processed.
    """
    checkpoint, _ = ProjectionCheckpoint.objects.get_or_create(
        projection_name=projection_name, defaults={"last_sequence": 0})

    events = (
        DomainEvent.objects
        .filter(global_sequence__gt=checkpoint.last_sequence)
        .order_by("global_sequence")[:batch_size]
    )

    processed = 0
    for event in events:
        projectors = get_projectors(event.event_type) + get_projectors("*")
        for projector in projectors:
            try:
                projector(event)
            except Exception:  # noqa: BLE001 — one bad projector must not wedge the stream
                logger.exception("Projector %s failed on event %s", projector, event.id)
        checkpoint.advance(event.global_sequence, event.id)
        processed += 1
    return processed


def rebuild_projection(*, projection_name: str = DEFAULT_PROJECTION) -> int:
    """Reset the checkpoint to 0 and replay the whole stream (idempotent projectors)."""
    ProjectionCheckpoint.objects.filter(projection_name=projection_name).update(
        last_sequence=0, last_event_id=None)
    return run_projections(projection_name=projection_name)
