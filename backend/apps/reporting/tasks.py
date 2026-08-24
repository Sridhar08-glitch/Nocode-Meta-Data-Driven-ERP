"""
Reporting Celery tasks (PROJECT_HANDBOOK.md §25.2).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from celery import shared_task

from .models import Report, ReportSnapshot
from .services import ReportService

SNAPSHOT_TTL_DAYS = 30


@shared_task(name="reporting.run_scheduled_report")
def run_scheduled_report(report_id: str) -> dict:
    report = Report.objects.filter(id=report_id, deleted_at__isnull=True).first()
    if report is None:
        return {"status": "missing"}
    snap = ReportService.take_snapshot(report, report.workspace_id)
    report.last_run_at = timezone.now()
    report.save(update_fields=["last_run_at"])
    recipients = report.schedule_recipients or []
    if recipients:
        try:
            from apps.notifications.services import NotificationService
            for rid in recipients:
                NotificationService.send(
                    recipient_id=rid, recipient_type="member",
                    template_slug="report_ready",
                    context={"event_type": "report_ready", "subject": f"Report: {report.name}",
                             "body": f"'{report.name}' ran with {snap.row_count} rows.",
                             "record_id": str(report.id)},
                    workspace_id=report.workspace_id, channels=["in_app"])
        except Exception:  # noqa: BLE001 — notification failure must not fail the report
            pass
    return {"status": "ok", "snapshot_id": str(snap.id), "rows": snap.row_count}


@shared_task(name="reporting.prune_old_snapshots")
def prune_old_snapshots() -> int:
    cutoff = timezone.now() - timedelta(days=SNAPSHOT_TTL_DAYS)
    deleted, _ = ReportSnapshot.objects.filter(created_at__lt=cutoff).delete()
    return deleted
