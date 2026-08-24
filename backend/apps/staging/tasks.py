"""
Import/Export Celery tasks (PROJECT_HANDBOOK.md §29.2).
"""
from __future__ import annotations

from django.utils import timezone

from celery import shared_task

from .models import ExportJob
from .services import ExportService, ImportService


@shared_task(name="staging.parse_import_file")
def parse_import_file(import_job_id: str) -> None:
    ImportService.parse_file(import_job_id)


@shared_task(name="staging.validate_import")
def validate_import(import_job_id: str) -> None:
    ImportService.validate_rows(import_job_id)


@shared_task(name="staging.execute_import")
def execute_import(import_job_id: str) -> None:
    ImportService.execute_import(import_job_id)


@shared_task(name="staging.execute_export")
def execute_export(export_job_id: str) -> None:
    ExportService.execute_export(export_job_id)


@shared_task(name="staging.expire_export_downloads")
def expire_export_downloads() -> int:
    """Daily beat: drop expired export artifacts from storage."""
    import contextlib

    from apps.documents.storage import get_storage_backend
    now = timezone.now()
    expired = ExportJob.objects.filter(
        status="completed", download_expires_at__lt=now).exclude(output_storage_key="")
    count = 0
    for job in expired:
        with contextlib.suppress(Exception):
            get_storage_backend(job.workspace_id).delete(job.output_storage_key)
        job.output_storage_key = ""
        job.save(update_fields=["output_storage_key"])
        count += 1
    return count
