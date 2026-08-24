"""
Search — full-text search index metadata and saved searches.
Actual FTS uses PostgreSQL tsvector; this module manages index configs and saved searches.
"""
from django.db import models

from apps.core.models import TenantModel, UUIDPrimaryKeyMixin


class SearchIndex(TenantModel):
    """
    Tracks which entity fields contribute to the FTS index for that entity.
    One row per entity definition.
    """
    entity_id = models.UUIDField(unique=True, db_index=True)
    entity_slug = models.CharField(max_length=63)

    # Field slugs that contribute to the tsvector
    indexed_field_slugs = models.JSONField(default=list)

    # Weight mapping: {"field_slug": "A"|"B"|"C"|"D"}
    field_weights = models.JSONField(default=dict)

    # When the index config was last updated (triggers Celery reindex task)
    config_updated_at = models.DateTimeField(null=True, blank=True)
    last_reindex_at = models.DateTimeField(null=True, blank=True)
    indexed_row_count = models.BigIntegerField(default=0)

    class Meta:
        db_table = "search_indexes"
        indexes = [models.Index(fields=["workspace_id"])]


class SavedSearch(TenantModel):
    """A named, reusable NQL search saved by a member."""
    name = models.CharField(max_length=255)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)

    # NQL AST
    nql_ast = models.JSONField()
    nql_source = models.TextField(blank=True)

    created_by = models.UUIDField()
    is_shared = models.BooleanField(default=False)  # visible to all workspace members

    class Meta:
        db_table = "saved_searches"
        indexes = [models.Index(fields=["workspace_id", "entity_id", "created_by"])]


class RecentSearch(UUIDPrimaryKeyMixin):
    """Rolling history of recent search queries per member (last 50)."""
    workspace_id = models.UUIDField(db_index=True)
    member_id = models.UUIDField(db_index=True)
    query_text = models.CharField(max_length=500)
    entity_slug = models.CharField(max_length=63, blank=True)
    result_count = models.IntegerField(default=0)
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recent_searches"
        indexes = [models.Index(fields=["workspace_id", "member_id", "-searched_at"])]
