"""
Core base models and mixins used across all Sridhar ERP apps.
"""
import uuid

from django.db import models
from django.utils import timezone


class UUIDPrimaryKeyMixin(models.Model):
    """All Sridhar ERP models use UUID primary keys."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.UUIDField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self, user_id=None):
        self.deleted_at = timezone.now()
        self.deleted_by = user_id
        self.save(update_fields=["deleted_at", "deleted_by"])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class AuditMixin(models.Model):
    created_by = models.UUIDField(null=True, blank=True)
    updated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        abstract = True


class TenantModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Base for all workspace-scoped models.
    workspace_id links to tenancy.Workspace — using UUID rather than FK
    to avoid cross-app ORM imports. RLS enforces isolation at DB level.
    """
    workspace_id = models.UUIDField(db_index=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.workspace_id:
            raise ValueError("workspace_id is required on all TenantModel instances")
        super().save(*args, **kwargs)


class EventVersionedMixin(models.Model):
    """Tracks the event version for optimistic concurrency."""
    _event_version = models.BigIntegerField(default=0)

    class Meta:
        abstract = True
