"""Tests for event store read-side query helpers."""
import uuid

import pytest
from django.test import TestCase

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.eventstore.query import (
    events_by_correlation,
    events_for_aggregate,
    latest_version,
)


def _persist(ws, agg_id, event_type="thing.created", version=1, correlation_id=None):
    ed = DomainEventData(
        event_type=event_type,
        workspace_id=ws,
        aggregate_type="Thing",
        aggregate_id=agg_id,
        payload={},
        actor_id=uuid.uuid4(),
        version=version,
        correlation_id=correlation_id or uuid.uuid4(),
    )
    return DomainEventFactory.persist_one(ed, set_rls_context=False)


@pytest.mark.django_db(transaction=True)
class TestQueryHelpers(TestCase):

    def setUp(self):
        self.ws = uuid.uuid4()
        self.agg_id = uuid.uuid4()

    def test_events_for_aggregate_ordered_by_version(self):
        _persist(self.ws, self.agg_id, version=1)
        _persist(self.ws, self.agg_id, version=2, event_type="thing.updated")
        _persist(self.ws, self.agg_id, version=3, event_type="thing.deleted")

        qs = events_for_aggregate(self.ws, "Thing", self.agg_id)
        versions = list(qs.values_list("version", flat=True))
        assert versions == [1, 2, 3]

    def test_events_for_aggregate_from_version(self):
        _persist(self.ws, self.agg_id, version=1)
        _persist(self.ws, self.agg_id, version=2, event_type="thing.updated")

        qs = events_for_aggregate(self.ws, "Thing", self.agg_id, from_version=2)
        assert qs.count() == 1
        assert qs.first().version == 2

    def test_events_for_aggregate_workspace_isolated(self):
        other_ws = uuid.uuid4()
        _persist(other_ws, self.agg_id, version=1)
        _persist(self.ws, self.agg_id, version=1)

        qs = events_for_aggregate(self.ws, "Thing", self.agg_id)
        assert qs.count() == 1

    def test_latest_version_no_events(self):
        assert latest_version(self.ws, "Thing", self.agg_id) == 0

    def test_latest_version_with_events(self):
        _persist(self.ws, self.agg_id, version=1)
        _persist(self.ws, self.agg_id, version=2, event_type="thing.updated")
        assert latest_version(self.ws, "Thing", self.agg_id) == 2

    def test_events_by_correlation(self):
        corr_id = uuid.uuid4()
        _persist(self.ws, self.agg_id, event_type="thing.created", version=1, correlation_id=corr_id)
        _persist(self.ws, self.agg_id, event_type="thing.tagged", version=2, correlation_id=corr_id)
        _persist(self.ws, self.agg_id, event_type="thing.other", version=3)  # different corr

        qs = events_by_correlation(self.ws, corr_id)
        assert qs.count() == 2
        assert all(str(e.correlation_id) == str(corr_id) for e in qs)
