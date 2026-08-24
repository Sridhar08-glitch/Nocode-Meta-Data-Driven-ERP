"""Tag attach/detach must emit domain events so the activity feed reflects them
(previously NOT emitted — the activity projector expects tag.attached/detached)."""
import uuid

import pytest

from apps.eventstore.models import DomainEvent
from apps.tagging import services as tagging


@pytest.mark.django_db
def test_attach_and_detach_emit_record_events():
    ws, entity_id, record_id, actor = (uuid.uuid4() for _ in range(4))
    tag = tagging.create_tag(workspace_id=ws, name="VIP", slug="vip")

    tagging.attach(workspace_id=ws, tag_id=tag.id, entity_id=entity_id,
                   record_id=record_id, by=actor)
    attached = DomainEvent.objects.filter(aggregate_id=record_id, event_type="tag.attached")
    assert attached.count() == 1
    assert attached.first().payload["tag_slug"] == "vip"

    tagging.detach(workspace_id=ws, tag_id=tag.id, record_id=record_id, by=actor)
    assert DomainEvent.objects.filter(aggregate_id=record_id, event_type="tag.detached").exists()


@pytest.mark.django_db
def test_idempotent_attach_emits_once():
    ws, entity_id, record_id = (uuid.uuid4() for _ in range(3))
    tag = tagging.create_tag(workspace_id=ws, name="Hot", slug="hot")
    tagging.attach(workspace_id=ws, tag_id=tag.id, entity_id=entity_id, record_id=record_id)
    tagging.attach(workspace_id=ws, tag_id=tag.id, entity_id=entity_id, record_id=record_id)
    # second attach is a no-op (already linked) → no duplicate event
    assert DomainEvent.objects.filter(
        aggregate_id=record_id, event_type="tag.attached").count() == 1
