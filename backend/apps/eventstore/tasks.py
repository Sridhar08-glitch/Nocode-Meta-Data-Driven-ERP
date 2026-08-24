"""
Celery tasks for async event projection.

These run OUTSIDE the original request transaction — they are enqueued
after the transaction commits, so projectors see committed data.
"""
from __future__ import annotations

import logging
import uuid

from django.db import transaction

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="eventstore.dispatch_event_to_projectors",
    max_retries=5,
    default_retry_delay=10,
    acks_late=True,
)
def dispatch_event_to_projectors(self, event_id: str) -> None:
    """
    Load a persisted DomainEvent by PK and fan out to all registered projectors.

    Projectors are functions registered via @event_projector(event_type).
    They update read models (Projection rows, physical-table rows, etc.).
    """
    from apps.eventstore.models import DomainEvent
    from apps.eventstore.projectors import get_projectors
    from apps.eventstore.rls import set_workspace_rls

    try:
        event = DomainEvent.objects.get(pk=uuid.UUID(event_id))
    except DomainEvent.DoesNotExist:
        logger.error("dispatch_event_to_projectors: event %s not found", event_id)
        return

    projectors = get_projectors(event.event_type) + get_projectors("*")
    if not projectors:
        logger.debug("No projectors for event_type=%s", event.event_type)
        return

    for projector_fn in projectors:
        try:
            with transaction.atomic():
                set_workspace_rls(str(event.workspace_id))
                projector_fn(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Projector %s failed for event %s (%s): %s",
                projector_fn.__qualname__,
                event_id,
                event.event_type,
                exc,
            )
            # Retry the whole task — projectors must be idempotent.
            raise self.retry(exc=exc) from exc


@shared_task(
    name="eventstore.rebuild_projections",
    max_retries=1,
)
def rebuild_projections(
    aggregate_type: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """
    Full projection rebuild for an aggregate type / workspace.

    Replays all domain events through registered projectors in global_sequence
    order.  Used for:
      - First-time projection creation
      - Recovery after projector bug fix
      - New projector registration (backfill)
    """
    from apps.eventstore.models import DomainEvent
    from apps.eventstore.projectors import get_projectors
    from apps.eventstore.rls import set_workspace_rls

    qs = DomainEvent.objects.order_by("global_sequence")
    if aggregate_type:
        qs = qs.filter(aggregate_type=aggregate_type)
    if workspace_id:
        qs = qs.filter(workspace_id=uuid.UUID(workspace_id))

    processed = 0
    errors = 0

    for event in qs.iterator(chunk_size=500):
        projectors = get_projectors(event.event_type) + get_projectors("*")
        for projector_fn in projectors:
            try:
                with transaction.atomic():
                    set_workspace_rls(str(event.workspace_id))
                    projector_fn(event)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Rebuild projector %s failed for event %s: %s",
                    projector_fn.__qualname__,
                    event.pk,
                    exc,
                )
                errors += 1

    logger.info(
        "rebuild_projections complete: processed=%d errors=%d aggregate_type=%s workspace=%s",
        processed,
        errors,
        aggregate_type,
        workspace_id,
    )
    return {"processed": processed, "errors": errors}
