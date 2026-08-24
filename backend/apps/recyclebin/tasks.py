"""Recycle bin Celery task (PROJECT_HANDBOOK.md §31.4)."""
from __future__ import annotations

from celery import shared_task

from .services import RecycleBinService


@shared_task(name="apps.recyclebin.tasks.auto_purge")
def auto_purge() -> int:
    """Beat: hard-delete recycle-bin entries past their retention window."""
    return RecycleBinService.purge_expired()
