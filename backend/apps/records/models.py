"""
Records — dynamic entity instances.
Physical entity tables (crm_leads, hr_employees…) are the primary storage.
`Record` is a metadata/overflow table for entities without promoted columns.
"""
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class Record(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Generic record row for entities that don't have a promoted physical table yet,
    OR as the overflow/metadata row pointing to a physical table row.
    """
    entity_id = models.UUIDField(db_index=True)        # EntityDefinition.id
    workspace_id = models.UUIDField(db_index=True)
    entity_slug = models.CharField(max_length=63, db_index=True)

    # Data: promoted columns can't be stored here, use physical table
    # custom_data holds JSONB overflow fields
    custom_data = models.JSONField(default=dict)

    # Standard system fields (denormalized for fast access)
    title = models.CharField(max_length=500, blank=True)  # computed from title_field_slug

    # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.UUIDField(null=True, blank=True)

    # Audit
    created_by = models.UUIDField(null=True, blank=True)
    updated_by = models.UUIDField(null=True, blank=True)

    # Event sourcing link
    _event_version = models.BigIntegerField(default=0)

    class Meta:
        db_table = "records"
        indexes = [
            models.Index(fields=["workspace_id", "entity_id"]),
            models.Index(fields=["workspace_id", "entity_slug"]),
            models.Index(fields=["deleted_at"]),
        ]

    def __str__(self):
        return f"Record:{self.entity_slug}:{self.id}"


class RecordVersion(UUIDPrimaryKeyMixin):
    """Snapshot of record state at a point in time (for field-level history)."""
    record_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    version_number = models.IntegerField()
    snapshot = models.JSONField()  # full field values at this version
    event_id = models.UUIDField(null=True, blank=True)  # DomainEvent that created this
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "record_versions"
        unique_together = [("record_id", "version_number")]
        indexes = [models.Index(fields=["record_id", "-version_number"])]


class RecordLock(UUIDPrimaryKeyMixin):
    """Optimistic/pessimistic lock on a record during concurrent edits."""
    record_id = models.UUIDField(unique=True, db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    locked_by = models.UUIDField()  # WorkspaceMember.id
    locked_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    session_id = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "record_locks"
