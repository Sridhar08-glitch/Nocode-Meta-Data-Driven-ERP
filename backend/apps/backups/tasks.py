"""Backups, restore, retention & expiry Celery tasks (PROJECT_HANDBOOK.md §33.3 / §33.4)."""
from __future__ import annotations

import contextlib

from django.utils import timezone

from celery import shared_task

from .models import BackupJob, DataRetentionPolicy
from .services import BackupService, RetentionService


@shared_task(name="apps.backups.tasks.execute_backup")
def execute_backup(job_id: str):
    BackupService.execute_backup(job_id)


@shared_task(name="apps.backups.tasks.execute_restore")
def execute_restore(job_id: str):
    BackupService.execute_restore(job_id)


@shared_task(name="apps.backups.tasks.nightly_backup_check")
def nightly_backup_check() -> int:
    """Beat (daily): start an automatic full backup for every active workspace."""
    from apps.tenancy.models import Workspace
    count = 0
    for ws in Workspace.objects.filter(is_active=True).iterator(chunk_size=200):
        BackupService.create_backup_job(
            workspace_id=ws.id, backup_type="full", is_automatic=True)
        count += 1
    return count


@shared_task(name="apps.backups.tasks.enforce_retention_policies")
def enforce_retention_policies() -> int:
    """Beat (nightly): enforce every active data-retention policy."""
    affected = 0
    for policy in DataRetentionPolicy.objects.filter(is_active=True).iterator(chunk_size=200):
        affected += RetentionService.enforce(policy)
    return affected


@shared_task(name="apps.backups.tasks.expire_old_backups")
def expire_old_backups() -> int:
    """Beat (daily): delete artifacts of backups past their expiry, mark them expired."""
    from apps.documents.storage import get_storage_backend
    now = timezone.now()
    expired = BackupJob.objects.filter(
        status="completed", expires_at__lt=now, expires_at__isnull=False)
    count = 0
    for job in expired.iterator(chunk_size=200):
        if job.storage_key:
            with contextlib.suppress(Exception):  # missing file must not block expiry
                get_storage_backend(job.workspace_id).delete(job.storage_key)
        job.status = "expired"
        job.storage_key = ""
        job.save(update_fields=["status", "storage_key"])
        count += 1
    return count
