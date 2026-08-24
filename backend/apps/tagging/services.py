"""Universal tagging (master spec §48) — tags attachable to any record."""
from __future__ import annotations

import uuid

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import RecordTag, Tag


def _emit_tag_event(*, workspace_id, event_type, record_id, payload, actor_id=None):
    """Emit a ``tag.attached`` / ``tag.detached`` domain event on the record aggregate.

    The activity projector (``apps/activity/projectors.py``) maps these to
    ``tag_added`` / ``tag_removed`` feed entries — without them, tag changes are
    invisible on the timeline.
    """
    from apps.eventstore.models import DomainEvent
    rid = uuid.UUID(str(record_id))
    version = DomainEvent.objects.filter(aggregate_id=rid).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="record", aggregate_id=rid, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def create_tag(*, workspace_id, name, slug, color="#6366f1", group="") -> Tag:
    tag, _ = Tag.objects.get_or_create(
        workspace_id=workspace_id, slug=slug,
        defaults={"name": name, "color": color, "group": group})
    return tag


def list_tags(*, workspace_id):
    return list(Tag.objects.filter(workspace_id=workspace_id).order_by("name"))


def attach(*, workspace_id, tag_id, entity_id, record_id, by=None) -> RecordTag:
    link, created = RecordTag.objects.get_or_create(
        workspace_id=workspace_id, tag_id=tag_id, record_id=record_id,
        defaults={"entity_id": entity_id, "attached_by": by})
    if created:
        tag = Tag.objects.filter(workspace_id=workspace_id, id=tag_id).first()
        _emit_tag_event(
            workspace_id=workspace_id, event_type="tag.attached", record_id=record_id,
            payload={"entity_id": str(entity_id), "tag_id": str(tag_id),
                     "tag_slug": tag.slug if tag else "", "tag_name": tag.name if tag else ""},
            actor_id=by)
    return link


def detach(*, workspace_id, tag_id, record_id, by=None) -> int:
    link = RecordTag.objects.filter(
        workspace_id=workspace_id, tag_id=tag_id, record_id=record_id).first()
    entity_id = link.entity_id if link else None
    deleted, _ = RecordTag.objects.filter(
        workspace_id=workspace_id, tag_id=tag_id, record_id=record_id).delete()
    if deleted:
        tag = Tag.objects.filter(workspace_id=workspace_id, id=tag_id).first()
        _emit_tag_event(
            workspace_id=workspace_id, event_type="tag.detached", record_id=record_id,
            payload={"entity_id": str(entity_id) if entity_id else None, "tag_id": str(tag_id),
                     "tag_slug": tag.slug if tag else "", "tag_name": tag.name if tag else ""},
            actor_id=by)
    return deleted


def tags_for_record(*, workspace_id, record_id):
    tag_ids = RecordTag.objects.filter(
        workspace_id=workspace_id, record_id=record_id).values_list("tag_id", flat=True)
    return list(Tag.objects.filter(workspace_id=workspace_id, id__in=list(tag_ids)).order_by("name"))
