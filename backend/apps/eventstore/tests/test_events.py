"""Tests for DomainEventData and DomainEventFactory."""
import uuid

import pytest
from django.test import TestCase

from apps.eventstore.events import DomainEventData, DomainEventFactory


def _make_event_data(ws=None, agg_id=None, version=1, event_type="thing.created"):
    return DomainEventData(
        event_type=event_type,
        workspace_id=ws or uuid.uuid4(),
        aggregate_type="Thing",
        aggregate_id=agg_id or uuid.uuid4(),
        payload={"key": "value"},
        actor_id=uuid.uuid4(),
        version=version,
    )


def test_domain_event_data_is_frozen():
    ed = _make_event_data()
    with pytest.raises((AttributeError, TypeError)):
        ed.event_type = "other"  # type: ignore[misc]


def test_domain_event_data_to_dict():
    ws = uuid.uuid4()
    agg = uuid.uuid4()
    ed = _make_event_data(ws=ws, agg_id=agg)
    d = ed.to_dict()
    assert d["event_type"] == "thing.created"
    assert d["workspace_id"] == str(ws)
    assert d["aggregate_id"] == str(agg)
    assert d["version"] == 1
    assert "occurred_at" in d


@pytest.mark.django_db(transaction=True)
class TestDomainEventFactory(TestCase):

    def test_persist_one(self):
        from apps.eventstore.models import DomainEvent

        ws = uuid.uuid4()
        agg = uuid.uuid4()
        ed = _make_event_data(ws=ws, agg_id=agg)

        event = DomainEventFactory.persist_one(ed, set_rls_context=False)

        assert event.pk is not None
        assert event.workspace_id == ws
        assert event.aggregate_id == agg
        assert event.event_type == "thing.created"
        assert event.payload == {"key": "value"}
        assert DomainEvent.objects.filter(pk=event.pk).count() == 1

    def test_persist_batch(self):
        from apps.eventstore.models import DomainEvent

        ws = uuid.uuid4()
        agg = uuid.uuid4()
        events_data = [
            _make_event_data(ws=ws, agg_id=agg, version=1, event_type="thing.created"),
            _make_event_data(ws=ws, agg_id=agg, version=2, event_type="thing.updated"),
        ]

        persisted = DomainEventFactory.persist_batch(events_data, set_rls_context=False)

        assert len(persisted) == 2
        assert DomainEvent.objects.filter(workspace_id=ws).count() == 2

    def test_persist_batch_empty_returns_empty(self):
        result = DomainEventFactory.persist_batch([], set_rls_context=False)
        assert result == []

    def test_persist_batch_mixed_workspaces_raises(self):
        ed1 = _make_event_data(ws=uuid.uuid4())
        ed2 = _make_event_data(ws=uuid.uuid4())

        with pytest.raises(ValueError, match="multiple workspaces"):
            DomainEventFactory.persist_batch([ed1, ed2], set_rls_context=False)

    def test_domain_event_immutable_after_save(self):

        ws = uuid.uuid4()
        agg = uuid.uuid4()
        ed = _make_event_data(ws=ws, agg_id=agg)
        event = DomainEventFactory.persist_one(ed, set_rls_context=False)

        # Attempting to save again (with existing pk) must raise
        with pytest.raises(ValueError, match="immutable"):
            event.save()
