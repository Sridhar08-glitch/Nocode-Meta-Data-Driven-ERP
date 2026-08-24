"""
Audit projection — the audit trail is a projection of the event store (§5.6/§11),
not a separate write path. Registered as a wildcard projector ("*") so every
persisted DomainEvent produces exactly one immutable AuditLog row.

Idempotent: keyed on ``event_id`` so re-runs / rebuilds never duplicate.
"""
from apps.eventstore.projectors import event_projector

from .models import AuditLog


@event_projector("*")
def project_audit(event) -> None:
    if AuditLog.objects.filter(event_id=event.id).exists():
        return  # already projected — idempotent
    payload = event.payload if isinstance(event.payload, dict) else {}
    AuditLog.objects.create(
        workspace_id=event.workspace_id,
        actor_id=event.actor_id,
        actor_type=event.actor_type or "user",
        http_method="",
        http_path="",
        http_status=0,
        resource_type=event.aggregate_type,
        resource_id=str(event.aggregate_id),
        action=event.event_type,
        changed_fields=list(payload.keys()),
        correlation_id=str(event.correlation_id) if event.correlation_id else "",
        event_id=event.id,
        occurred_at=event.occurred_at,
    )
