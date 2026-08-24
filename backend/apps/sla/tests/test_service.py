"""SLAService attach / pause / resume / mark_met (PROJECT_HANDBOOK.md §28.2 / §28.5)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.sla.models import SLARecord
from apps.sla.services import SLAService

TARGETS = [{"metric": "resolution", "target_minutes": 120, "warning_at_percent": 50}]


@pytest.mark.django_db
class TestAttach:
    def test_applies_when_filters(self, ws, lead, make_policy):
        make_policy(TARGETS, applies_when="priority = \"high\"")
        hot = SLAService.attach_policies(
            record_id=__import__("uuid").uuid4(), entity_slug="lead",
            record_data={"priority": "high"}, workspace_id=ws.id, entity_id=lead.id)
        assert len(hot) == 1
        cold = SLAService.attach_policies(
            record_id=__import__("uuid").uuid4(), entity_slug="lead",
            record_data={"priority": "low"}, workspace_id=ws.id, entity_id=lead.id)
        assert cold == []

    def test_attach_creates_one_per_metric(self, ws, lead, make_policy):
        make_policy([{"metric": "first_response", "target_minutes": 30},
                     {"metric": "resolution", "target_minutes": 240}])
        rid = __import__("uuid").uuid4()
        records = SLAService.attach_policies(
            record_id=rid, entity_slug="lead", record_data={}, workspace_id=ws.id,
            entity_id=lead.id)
        assert {r.metric_key for r in records} == {"first_response", "resolution"}


@pytest.mark.django_db
class TestPauseResume:
    def _rec(self, ws, lead):
        now = timezone.now()
        return SLARecord.objects.create(
            policy_id=__import__("uuid").uuid4(), workspace_id=ws.id, entity_id=lead.id,
            record_id=__import__("uuid").uuid4(), metric_key="resolution",
            status="on_track", started_at=now,
            target_at=now + dt.timedelta(hours=2), warning_at=now + dt.timedelta(hours=1))

    def test_pause_accumulates_across_cycles(self, ws, lead):
        rec = self._rec(ws, lead)
        original_target = rec.target_at
        # cycle 1: pause then backdate paused_at by 600s, resume
        SLAService.pause_record(rec.record_id, ws.id)
        SLARecord.objects.filter(id=rec.id).update(
            paused_at=timezone.now() - dt.timedelta(seconds=600))
        SLAService.resume_record(rec.record_id, ws.id)
        rec.refresh_from_db()
        assert rec.paused_seconds >= 600
        assert rec.status == "on_track"
        assert rec.target_at > original_target   # shifted later by the pause
        # cycle 2
        SLAService.pause_record(rec.record_id, ws.id)
        SLARecord.objects.filter(id=rec.id).update(
            paused_at=timezone.now() - dt.timedelta(seconds=300))
        SLAService.resume_record(rec.record_id, ws.id)
        rec.refresh_from_db()
        assert rec.paused_seconds >= 900


@pytest.mark.django_db
class TestMarkMet:
    def test_mark_met(self, ws, lead):
        now = timezone.now()
        rec = SLARecord.objects.create(
            policy_id=__import__("uuid").uuid4(), workspace_id=ws.id, entity_id=lead.id,
            record_id=__import__("uuid").uuid4(), metric_key="resolution",
            status="on_track", started_at=now,
            target_at=now + dt.timedelta(hours=1), warning_at=now + dt.timedelta(minutes=30))
        SLAService.mark_met(rec.record_id, "resolution", ws.id)
        rec.refresh_from_db()
        assert rec.status == "met" and rec.met_at is not None
