"""
Recycle Bin — soft-deleted records staged for permanent deletion.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class RecycleBinEntry(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    References a soft-deleted record.
    The record remains in its physical table with deleted_at set.
    This table drives the UI and scheduled hard-delete job.
    """
    workspace_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField(db_index=True)
    entity_slug = models.CharField(max_length=63)
    record_id = models.UUIDField(db_index=True)

    # Snapshot of title at time of deletion (for display after physical table may change)
    record_title = models.CharField(max_length=500, blank=True)

    deleted_by = models.UUIDField(null=True, blank=True)
    deleted_at = models.DateTimeField(db_index=True)

    # When this entry is scheduled for permanent hard-delete
    purge_after = models.DateTimeField(db_index=True)

    # Optional: track cascade-deleted children
    cascade_entries = models.JSONField(default=list)  # [{entity_slug, record_id}]

    is_purged = models.BooleanField(default=False)
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recycle_bin_entries"
        unique_together = [("workspace_id", "record_id")]
        indexes = [
            models.Index(fields=["workspace_id", "is_purged", "purge_after"]),
        ]
