"""
Activity projector (PROJECT_HANDBOOK.md §23.1).

A wildcard (``"*"``) projector that turns domain events into human-readable
``ActivityEntry`` rows on a record's timeline. Idempotent on ``event_id`` so
re-runs / rebuilds never duplicate. Events that don't map to a user-facing
activity type, or that can't be tied to a record, are skipped.
"""
from __future__ import annotations

import logging

from apps.eventstore.projectors import event_projector
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import ActivityEntry

logger = logging.getLogger(__name__)

# domain event type → ActivityEntry.activity_type
EVENT_ACTIVITY_MAP = {
    "record.created": "record_created",
    "record.updated": "record_updated",
    "record.deleted": "record_deleted",
    "record.restored": "record_restored",
    "record.stage_entered": "stage_changed",
    "comment.created": "comment_added",
    "comment.updated": "comment_edited",
    "comment.deleted": "comment_deleted",
    "file.attached": "file_attached",
    "file.removed": "file_removed",
    "relationship.linked": "relationship_linked",
    "relationship.unlinked": "relationship_unlinked",
    "workflow.run.started": "workflow_started",
    "workflow.run.completed": "workflow_completed",
    "workflow.run.failed": "workflow_failed",
    "approval.requested": "approval_requested",
    "approval.approved": "approval_approved",
    "approval.rejected": "approval_rejected",
    "assignment.changed": "assignment_changed",
    "tag.attached": "tag_added",
    "tag.detached": "tag_removed",
    "sla.warning": "sla_warning",
    "sla.breached": "sla_breached",
    "sla.met": "sla_met",
    "email.sent": "email_sent",
    "note.added": "note_added",
}

_PII_MASK = "***"


def project_field_diff(before: dict, after: dict, field_defs) -> dict:
    """Return ``{slug: {"before", "after", "label"}}`` for changed fields only.

    Fields whose definition is marked PII (``config.is_pii``) have their values
    masked. ``field_defs`` items may be ``FieldDefinition`` rows or plain dicts
    (``{slug, label, is_pii}``) so the helper is usable from tests directly.
    """
    meta = {}
    for fd in field_defs or []:
        if isinstance(fd, dict):
            slug = fd.get("slug")
            label = fd.get("label") or slug
            is_pii = bool(fd.get("is_pii"))
        else:
            slug = fd.slug
            label = getattr(fd, "name", "") or slug
            is_pii = bool((getattr(fd, "config", None) or {}).get("is_pii"))
        meta[slug] = (label, is_pii)

    diff = {}
    for key in set(before or {}) | set(after or {}):
        old, new = (before or {}).get(key), (after or {}).get(key)
        if old == new:
            continue
        label, is_pii = meta.get(key, (key, False))
        if is_pii:
            old = _PII_MASK if old is not None else None
            new = _PII_MASK if new is not None else None
        diff[key] = {"before": old, "after": new, "label": label}
    return diff


def _resolve_entity(workspace_id, slug):
    if not slug:
        return None
    try:
        return SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=slug)
    except EntityNotFoundError:
        return None


def _resolve_targets(event, payload):
    """Return (entity_id, record_id) or (None, None) when not record-scoped."""
    record_id = payload.get("record_id")
    entity_id = payload.get("entity_id")
    if record_id is None and event.aggregate_type == "record":
        record_id = event.aggregate_id
    entity = None
    if entity_id is None:
        entity = _resolve_entity(event.workspace_id, payload.get("entity_slug"))
        if entity is not None:
            entity_id = entity.id
    if (record_id is None or entity_id is None) and event.aggregate_type == "workflow_run":
        from apps.workflows.models import WorkflowRun
        run = WorkflowRun.objects.filter(id=event.aggregate_id).first()
        if run is not None:
            record_id = record_id or run.record_id
            entity_id = entity_id or run.entity_id
    return entity_id, record_id, entity


def _actor_name(actor_id) -> str:
    if not actor_id:
        return ""
    from apps.accounts.models import User
    user = User.objects.filter(id=actor_id).only("full_name", "email").first()
    if user is None:
        return ""
    return user.full_name or user.email or ""


def _changes_for(event, payload, entity):
    if event.event_type != "record.updated":
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    field_defs = list(entity.fields.filter(is_deleted=False)) if entity is not None else []
    diff = project_field_diff({}, data, field_defs)
    return [{"field_slug": slug, "field_label": d["label"],
             "old": d["before"], "new": d["after"]} for slug, d in diff.items()]


def _summary(activity_type, actor_name, payload) -> str:
    who = actor_name or "Someone"
    text = {
        "record_created": f"{who} created this record",
        "record_updated": f"{who} updated this record",
        "record_deleted": f"{who} deleted this record",
        "record_restored": f"{who} restored this record",
        "stage_changed": f"{who} changed the stage to {payload.get('stage', '')}".strip(),
        "comment_added": f"{who} commented",
        "comment_edited": f"{who} edited a comment",
        "comment_deleted": f"{who} deleted a comment",
        "workflow_started": "A workflow started",
        "workflow_completed": "A workflow completed",
        "workflow_failed": "A workflow failed",
        "approval_requested": f"{who} requested approval",
        "approval_approved": f"{who} approved",
        "approval_rejected": f"{who} rejected",
        "assignment_changed": f"{who} changed the assignee",
        "tag_added": f"{who} added a tag",
        "tag_removed": f"{who} removed a tag",
    }.get(activity_type, f"{who}: {activity_type.replace('_', ' ')}")
    return text


@event_projector("*")
def project_activity(event) -> None:
    activity_type = EVENT_ACTIVITY_MAP.get(event.event_type)
    if activity_type is None:
        return  # not a user-facing activity
    if ActivityEntry.objects.filter(event_id=event.id).exists():
        return  # idempotent
    payload = event.payload if isinstance(event.payload, dict) else {}
    entity_id, record_id, entity = _resolve_targets(event, payload)
    if entity_id is None or record_id is None:
        return  # cannot place on a record timeline
    actor_name = _actor_name(event.actor_id)
    ActivityEntry.objects.create(
        workspace_id=event.workspace_id, entity_id=entity_id, record_id=record_id,
        activity_type=activity_type, actor_id=event.actor_id,
        actor_type=event.actor_type or "user", actor_name=actor_name,
        summary=_summary(activity_type, actor_name, payload),
        changes=_changes_for(event, payload, entity),
        event_id=event.id, event_sequence=event.global_sequence,
        occurred_at=event.occurred_at)
