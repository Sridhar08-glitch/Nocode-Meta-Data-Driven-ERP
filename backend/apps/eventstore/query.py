"""
Event store read-side helpers.

These functions query the domain_events table for common read patterns.
All are workspace-scoped (ORM filter is first line; RLS is second).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.db.models import QuerySet

if TYPE_CHECKING:
    pass


def events_for_aggregate(
    workspace_id: uuid.UUID,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    *,
    from_version: int = 0,
) -> QuerySet:
    """
    Return all events for a specific aggregate, ordered by version ascending.
    Used to replay aggregate state (event sourcing pattern).
    """
    from apps.eventstore.models import DomainEvent  # local import

    return (
        DomainEvent.objects.filter(
            workspace_id=workspace_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            version__gte=from_version,
        )
        .order_by("version")
    )


def latest_version(
    workspace_id: uuid.UUID,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
) -> int:
    """Return the current (highest) version for an aggregate, or 0 if none."""
    from apps.eventstore.models import DomainEvent

    result = (
        DomainEvent.objects.filter(
            workspace_id=workspace_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
        )
        .values_list("version", flat=True)
        .order_by("-version")
        .first()
    )
    return result if result is not None else 0


def events_since_sequence(
    workspace_id: uuid.UUID,
    since_sequence: int,
    *,
    event_types: list[str] | None = None,
    limit: int = 1000,
) -> QuerySet:
    """
    Return events after *since_sequence* for a workspace.
    Used by projection catch-up / subscription feeds.
    """
    from apps.eventstore.models import DomainEvent

    qs = DomainEvent.objects.filter(
        workspace_id=workspace_id,
        global_sequence__gt=since_sequence,
    ).order_by("global_sequence")

    if event_types:
        qs = qs.filter(event_type__in=event_types)

    return qs[:limit]


def events_by_correlation(
    workspace_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> QuerySet:
    """Return all events sharing a correlation_id (one command = one correlation)."""
    from apps.eventstore.models import DomainEvent

    return DomainEvent.objects.filter(
        workspace_id=workspace_id,
        correlation_id=correlation_id,
    ).order_by("global_sequence")
