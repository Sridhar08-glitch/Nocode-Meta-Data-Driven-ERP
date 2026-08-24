"""Reporting Celery tasks (PROJECT_HANDBOOK.md §25.2 / §25.4)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications.models import Notification
from apps.reporting.models import ReportSnapshot
from apps.reporting.tasks import prune_old_snapshots, run_scheduled_report


@pytest.mark.django_db
class TestScheduledReport:
    def test_run_creates_snapshot_and_notifies(self, ws, user, leads, make_report):
        report = make_report()
        report.schedule_recipients = [str(user.id)]
        report.save(update_fields=["schedule_recipients"])
        result = run_scheduled_report(str(report.id))
        assert result["status"] == "ok"
        assert ReportSnapshot.objects.filter(report_id=report.id).count() == 1
        report.refresh_from_db()
        assert report.last_run_at is not None
        assert Notification.objects.filter(workspace_id=ws.id, recipient_id=user.id).exists()

    def test_run_missing_report(self):
        import uuid
        assert run_scheduled_report(str(uuid.uuid4()))["status"] == "missing"


@pytest.mark.django_db
class TestPrune:
    def test_prunes_old_snapshots(self, ws, leads, make_report):
        report = make_report()
        old = ReportSnapshot.objects.create(report_id=report.id, workspace_id=ws.id,
                                            row_count=1, data=[])
        ReportSnapshot.objects.filter(id=old.id).update(
            created_at=timezone.now() - timedelta(days=40))
        fresh = ReportSnapshot.objects.create(report_id=report.id, workspace_id=ws.id,
                                              row_count=1, data=[])
        deleted = prune_old_snapshots()
        assert deleted == 1
        assert ReportSnapshot.objects.filter(id=fresh.id).exists()
        assert not ReportSnapshot.objects.filter(id=old.id).exists()
