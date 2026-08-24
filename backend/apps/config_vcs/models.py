"""
Configuration VCS — Git-for-config: commit/diff/branch/merge/rollback.
Tracks versions of EntityDefinitions, FieldDefinitions, WorkflowDefinitions,
BusinessRules, Views, Dashboards, Reports.
"""
from django.db import models

from apps.core.models import TenantModel


class ConfigCommit(TenantModel):
    """
    A snapshot of all (or changed) configuration objects at a point in time.
    Append-only. Hash computed from content for integrity.
    """
    sha = models.CharField(max_length=64, db_index=True)  # SHA-256 of payload
    parent_sha = models.CharField(max_length=64, blank=True)  # previous commit
    message = models.CharField(max_length=500)
    branch = models.CharField(max_length=100, default="main")

    # Snapshot of all config objects (full state, not just diff)
    payload = models.JSONField()  # {"entities": [...], "fields": [...], ...}

    # Computed diff from parent (stored for fast display)
    diff = models.JSONField(default=dict)

    author_id = models.UUIDField(null=True, blank=True)

    # Auto-commit tags: "schema_change", "import", "workflow_publish" etc.
    tags = models.JSONField(default=list)

    class Meta:
        db_table = "config_commits"
        unique_together = [("workspace_id", "sha")]
        indexes = [
            models.Index(fields=["workspace_id", "branch", "-created_at"]),
        ]


class ConfigBranch(TenantModel):
    """A named pointer to a config commit (like a git branch)."""
    name = models.CharField(max_length=100)
    head_sha = models.CharField(max_length=64)
    base_sha = models.CharField(max_length=64, blank=True)
    is_default = models.BooleanField(default=False)
    is_protected = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "config_branches"
        unique_together = [("workspace_id", "name")]


class ConfigMergeRequest(TenantModel):
    """
    A proposal to merge one config branch into another (like a Pull Request).
    """
    STATUS = [
        ("open", "Open"),
        ("merged", "Merged"),
        ("closed", "Closed"),
        ("conflict", "Conflict"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_branch = models.CharField(max_length=100)
    target_branch = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS, default="open")

    conflict_details = models.JSONField(default=list)
    resolution = models.JSONField(default=dict)

    opened_by = models.UUIDField()
    merged_by = models.UUIDField(null=True, blank=True)
    merged_at = models.DateTimeField(null=True, blank=True)
    merge_commit_sha = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "config_merge_requests"
        indexes = [models.Index(fields=["workspace_id", "status"])]
