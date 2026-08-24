"""
Projector registry.

Projectors are functions that update read models (materialized views,
Projection rows, physical-table records, search indexes, etc.) in response
to persisted DomainEvents.

They differ from in-process subscribers (@event_subscriber) in that they
run asynchronously, AFTER the originating transaction commits.

Registration:
    @event_projector("record.created", "record.updated")
    def project_record(event: DomainEvent) -> None:
        ...

Requirements:
    - Must be IDEMPOTENT: they may be called multiple times for the same event
      (Celery retries, rebuild tasks).
    - Should be fast; hand off heavy work to nested Celery tasks.
    - Must not raise on non-fatal errors — log and return.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# { event_type: [projector_fn, ...] }
_PROJECTOR_REGISTRY: dict[str, list[Callable]] = {}


def event_projector(*event_types: str):
    """
    Decorator to register an async projector for one or more event types.

    Example:
        @event_projector("record.created")
        def project_record_created(event: DomainEvent) -> None:
            from apps.records.models import Record
            Record.objects.update_or_create(
                id=event.aggregate_id,
                defaults={...event.payload},
            )
    """
    def decorator(fn: Callable) -> Callable:
        for event_type in event_types:
            _PROJECTOR_REGISTRY.setdefault(event_type, []).append(fn)
            logger.debug("Registered projector %s → %s", event_type, fn.__qualname__)
        return fn
    return decorator


def get_projectors(event_type: str) -> list[Callable]:
    """Return all projectors for *event_type*."""
    return list(_PROJECTOR_REGISTRY.get(event_type, []))


def get_all_projector_event_types() -> list[str]:
    """Return every event type that has at least one projector."""
    return list(_PROJECTOR_REGISTRY.keys())


def clear_projectors() -> None:
    """ONLY for tests."""
    _PROJECTOR_REGISTRY.clear()
