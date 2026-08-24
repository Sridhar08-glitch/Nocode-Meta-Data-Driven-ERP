import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("nexus")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Drain the event stream into read models (audit, record projections) every minute
    "drain-projections": {
        "task": "apps.projections.tasks.drain_projections",
        "schedule": crontab(),
    },
    # Projection health-check every 5 minutes
    "projection-health-check": {
        "task": "apps.projections.tasks.health_check",
        "schedule": crontab(minute="*/5"),
    },
    # SLA breach/warning sweep every 5 minutes
    "sla-tick": {
        "task": "sla.check_sla_breaches",
        "schedule": crontab(minute="*/5"),
    },
    # Fire due scheduled workflows every minute
    "fire-scheduled-workflows": {
        "task": "workflows.fire_scheduled_workflows",
        "schedule": crontab(),
    },
    # Fail workflow runs stuck running > 24h, hourly
    "cancel-stalled-workflow-runs": {
        "task": "workflows.cancel_stalled_runs",
        "schedule": crontab(minute=0),
    },
    # Prune report snapshots older than 30 days, daily
    "prune-report-snapshots": {
        "task": "reporting.prune_old_snapshots",
        "schedule": crontab(hour=3, minute=30),
    },
    # Resolve timed-out approval requests every 15 minutes
    "check-approval-timeout": {
        "task": "approvals.check_approval_timeout",
        "schedule": crontab(minute="*/15"),
    },
    # Expire export download artifacts, daily
    "expire-export-downloads": {
        "task": "staging.expire_export_downloads",
        "schedule": crontab(hour=4, minute=30),
    },
    # Retry failed webhook deliveries, hourly
    "retry-failed-webhooks": {
        "task": "integrations.retry_failed_deliveries",
        "schedule": crontab(minute=15),
    },
    # Nightly backup reminder
    "daily-backup-check": {
        "task": "apps.backups.tasks.nightly_backup_check",
        "schedule": crontab(hour=2, minute=0),
    },
    # Data retention enforcement nightly
    "enforce-data-retention": {
        "task": "apps.backups.tasks.enforce_retention_policies",
        "schedule": crontab(hour=3, minute=0),
    },
    # Recycle bin auto-purge weekly
    "purge-recyclebin": {
        "task": "apps.recyclebin.tasks.auto_purge",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
    # Expire backup artifacts past their retention window, daily
    "expire-old-backups": {
        "task": "apps.backups.tasks.expire_old_backups",
        "schedule": crontab(hour=2, minute=30),
    },
    # Permanently purge soft-deleted workspaces past retention, daily
    "purge-expired-workspaces": {
        "task": "apps.tenancy.tasks.purge_expired_workspaces",
        "schedule": crontab(hour=4, minute=30),
    },
    # Collections (F2): charge overdue late fees daily
    "collections-late-fees": {
        "task": "collections.run_late_fees",
        "schedule": crontab(hour=1, minute=30),
    },
    # Collections (F2): send due/overdue reminders daily
    "collections-reminders": {
        "task": "collections.run_reminders",
        "schedule": crontab(hour=6, minute=0),
    },
    # Collections (F2): escalate dunning on overdue installments daily
    "collections-dunning": {
        "task": "collections.run_dunning",
        "schedule": crontab(hour=6, minute=30),
    },
}
