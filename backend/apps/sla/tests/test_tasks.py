"""SLA breach/warning sweep (PROJECT_HANDBOOK.md §28.3 / §28.5)."""
import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.notifications.models import Notification
from apps.sla.models import SLARecord
from apps.sla.tasks import check_sla_breaches


def _rec(ws, lead, policy_id, *, warning_delta, target_delta, status="on_track"):
    now = timezone.now()
    return SLARecord.objects.create(
        policy_id=policy_id, workspace_id=ws.id, entity_id=lead.id,
        record_id=uuid.uuid4(), metric_key="resolution", status=status,
        started_at=now - dt.timedelta(hours=3),
        warning_at=now + dt.timedelta(minutes=warning_delta),
        target_at=now + dt.timedelta(minutes=target_delta))


@pytest.mark.django_db
class TestBreachSweep:
    def test_on_track_to_warning(self, ws, lead, make_policy):
        policy = make_policy([{"metric": "resolution", "target_minutes": 60}])
        rec = _rec(ws, lead, policy.id, warning_delta=-1, target_delta=60)  # warning passed
        check_sla_breaches()
        rec.refresh_from_db()
        assert rec.status == "warning" and rec.warning_sent

    def test_warning_to_breached(self, ws, lead, make_policy):
        policy = make_policy([{"metric": "resolution", "target_minutes": 60}])
        rec = _rec(ws, lead, policy.id, warning_delta=-30, target_delta=-1, status="warning")
        check_sla_breaches()
        rec.refresh_from_db()
        assert rec.status == "breached" and rec.breached_at is not None

    def test_breach_notifies_once(self, ws, user, lead, make_policy):
        policy = make_policy([{"metric": "resolution", "target_minutes": 60}],
                             escalation=[{"type": "notify", "recipient_id": str(user.id)}])
        rec = _rec(ws, lead, policy.id, warning_delta=-30, target_delta=-1)
        check_sla_breaches()
        check_sla_breaches()   # second sweep: already breached → no re-notify
        assert Notification.objects.filter(
            workspace_id=ws.id, recipient_id=user.id).count() == 1
        rec.refresh_from_db()
        assert rec.status == "breached"

    def test_paused_and_met_skipped(self, ws, lead, make_policy):
        policy = make_policy([{"metric": "resolution", "target_minutes": 60}])
        paused = _rec(ws, lead, policy.id, warning_delta=-30, target_delta=-1, status="paused")
        paused.paused_at = timezone.now()
        paused.save(update_fields=["paused_at"])
        met = _rec(ws, lead, policy.id, warning_delta=-30, target_delta=-1, status="met")
        check_sla_breaches()
        paused.refresh_from_db()
        met.refresh_from_db()
        assert paused.status == "paused"
        assert met.status == "met"
