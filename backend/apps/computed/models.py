"""
Computed fields — formula, rollup, count.
Evaluation results are cached here and invalidated on dependency change.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class ComputedFieldCache(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Cached result for a single computed field on a single record.
    Invalidated when source fields/records change.
    """
    workspace_id = models.UUIDField(db_index=True)
    field_id = models.UUIDField(db_index=True)        # FieldDefinition (formula/rollup/count)
    record_id = models.UUIDField(db_index=True)

    # Stored result (typed value as JSON scalar)
    cached_value = models.JSONField(null=True, blank=True)
    is_stale = models.BooleanField(default=False, db_index=True)
    computed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Dependency fingerprint — hash of source values used for this computation
    dep_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "computed_field_cache"
        unique_together = [("workspace_id", "field_id", "record_id")]
        indexes = [models.Index(fields=["workspace_id", "is_stale"])]


class ComputedFieldDependency(UUIDPrimaryKeyMixin):
    """
    Tracks which source fields a computed field depends on.
    Used to know which caches to invalidate when a field value changes.
    """
    workspace_id = models.UUIDField(db_index=True)
    computed_field_id = models.UUIDField(db_index=True)   # the formula/rollup field

    # Dependency is either a field in the same entity or via relationship
    dep_entity_id = models.UUIDField()
    dep_field_id = models.UUIDField(db_index=True)
    dep_relationship_id = models.UUIDField(null=True, blank=True)  # if via lookup

    class Meta:
        db_table = "computed_field_dependencies"
        unique_together = [("computed_field_id", "dep_entity_id", "dep_field_id")]
        indexes = [models.Index(fields=["dep_field_id"])]
