"""
Celery tasks for the projection runner.

``drain_projections`` advances every registered projector (incl. the wildcard
audit projector) over new events; scheduled by Celery beat. ``health_check``
reports how far each projection lags behind the event stream.
"""
from celery import shared_task

from .services import run_projections


@shared_task
def drain_projections(projection_name: str = "default") -> int:
    """Process all new events into read models. Returns events processed."""
    return run_projections(projection_name=projection_name)


@shared_task
def health_check() -> dict:
    """Report projection lag (latest global_sequence vs each checkpoint)."""
    from apps.eventstore.models import DomainEvent, ProjectionCheckpoint

    latest = (DomainEvent.objects.order_by("-global_sequence")
              .values_list("global_sequence", flat=True).first()) or 0
    checkpoints = list(ProjectionCheckpoint.objects.values("projection_name", "last_sequence"))
    return {
        "latest_sequence": latest,
        "lag": {c["projection_name"]: latest - (c["last_sequence"] or 0) for c in checkpoints},
    }
