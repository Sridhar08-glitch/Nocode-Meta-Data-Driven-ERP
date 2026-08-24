"""SLA REST API (PROJECT_HANDBOOK.md §28.4 / §28.5)."""
import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.sla.models import SLARecord

BASE = "/api/v1/sla"
DATA = "/api/v1/data/lead"


@pytest.mark.django_db
class TestPolicyApi:
    def test_policy_crud(self, client, lead):
        r = client.post(f"{BASE}/policies/",
                        {"name": "P", "slug": "p", "entity_id": str(lead.id),
                         "targets": [{"metric": "resolution", "target_minutes": 60}]},
                        format="json")
        assert r.status_code == 201, r.content
        pid = r.json()["id"]
        assert client.get(f"{BASE}/policies/").json()["count"] == 1
        assert client.delete(f"{BASE}/policies/{pid}/").status_code == 204

    def test_business_hours_crud(self, client):
        r = client.post(f"{BASE}/business-hours/",
                        {"name": "BH", "timezone": "UTC",
                         "schedule": {"mon": {"start": "09:00", "end": "17:00"}}},
                        format="json")
        assert r.status_code == 201
        assert client.get(f"{BASE}/business-hours/").json()["count"] == 1


@pytest.mark.django_db
class TestRecordSLAApi:
    def _rec(self, ws, lead, record_id):
        now = timezone.now()
        return SLARecord.objects.create(
            policy_id=uuid.uuid4(), workspace_id=ws.id, entity_id=lead.id,
            record_id=record_id, metric_key="resolution", status="on_track",
            started_at=now, target_at=now + dt.timedelta(hours=2),
            warning_at=now + dt.timedelta(hours=1))

    def test_record_sla_status_pause_resume(self, ws, lead, client):
        rid = uuid.uuid4()
        self._rec(ws, lead, rid)
        assert client.get(f"{DATA}/{rid}/sla/").json()["count"] == 1
        assert client.post(f"{DATA}/{rid}/sla/pause/").json()["paused"] == 1
        assert SLARecord.objects.get(record_id=rid).status == "paused"
        assert client.post(f"{DATA}/{rid}/sla/resume/").json()["resumed"] == 1
        assert SLARecord.objects.get(record_id=rid).status == "on_track"

    def test_dashboard(self, ws, lead, client):
        self._rec(ws, lead, uuid.uuid4())
        body = client.get(f"{BASE}/dashboard/").json()
        assert body["on_track"] == 1
        assert "breached" in body and "warning" in body


@pytest.mark.django_db
class TestAttachOnCreate:
    def test_policy_attached_on_record_create(self, ws, member, lead, client):
        client.post(f"{BASE}/policies/",
                    {"name": "P", "slug": "p", "entity_id": str(lead.id),
                     "applies_when_nql": "priority = \"high\"",
                     "targets": [{"metric": "resolution", "target_minutes": 60}]},
                    format="json")
        r = client.post(f"{DATA}/", {"priority": "high"}, format="json")
        assert r.status_code == 201
        rid = r.json()["id"]
        assert SLARecord.objects.filter(workspace_id=ws.id, record_id=rid).count() == 1
