"""Tenancy background jobs."""
from celery import shared_task


@shared_task
def purge_expired_workspaces():
    """Permanently delete soft-deleted workspaces past their retention window."""
    from apps.tenancy.services import WorkspaceService
    return WorkspaceService.purge_expired_workspaces()
