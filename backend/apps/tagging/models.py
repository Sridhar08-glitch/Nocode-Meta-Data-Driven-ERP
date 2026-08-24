"""
Tagging — workspace-scoped labels attachable to any record or document.
"""
from django.db import models

from apps.core.models import TenantModel, UUIDPrimaryKeyMixin


class Tag(TenantModel):
    """Workspace-scoped tag definition."""
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#6366f1")  # hex color
    description = models.CharField(max_length=255, blank=True)
    group = models.CharField(max_length=100, blank=True)  # optional grouping

    class Meta:
        db_table = "tags"
        unique_together = [("workspace_id", "slug")]
        indexes = [models.Index(fields=["workspace_id", "group"])]


class RecordTag(UUIDPrimaryKeyMixin):
    """Many-to-many link between a tag and any record."""
    workspace_id = models.UUIDField(db_index=True)
    tag_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()
    record_id = models.UUIDField(db_index=True)
    attached_by = models.UUIDField(null=True, blank=True)
    attached_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "record_tags"
        unique_together = [("workspace_id", "tag_id", "record_id")]
        indexes = [models.Index(fields=["workspace_id", "record_id"])]


class DocumentTag(UUIDPrimaryKeyMixin):
    """Many-to-many link between a tag and a document."""
    workspace_id = models.UUIDField(db_index=True)
    tag_id = models.UUIDField(db_index=True)
    document_id = models.UUIDField(db_index=True)
    attached_by = models.UUIDField(null=True, blank=True)
    attached_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_tags"
        unique_together = [("workspace_id", "tag_id", "document_id")]
