"""
Feature Flags (Phase 1.29).

Per-workspace module/beta toggles with deterministic %-rollout and per-role / per-user /
per-workspace overrides. Resolved flags are surfaced to the shell via ``/feature-flags/active/``.
Both tables are workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel


class FeatureFlag(TenantModel):
    SCOPE_CHOICES = [
        ("workspace", "Workspace"),
        ("role", "Role"),
        ("user", "User"),
        ("global", "Global"),
    ]

    key = models.SlugField(max_length=100)               # e.g. "new_dashboard"
    name = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)         # master switch (default state)
    rollout_percent = models.IntegerField(default=100)   # 0–100 deterministic rollout when enabled
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="workspace")
    config = models.JSONField(default=dict)              # optional payload returned with the flag
    is_active = models.BooleanField(default=True)        # soft-disable the flag definition itself
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "feature_flags"
        unique_together = [("workspace_id", "key")]
        indexes = [models.Index(fields=["workspace_id", "key"])]

    def __str__(self):
        return f"{self.key} ({'on' if self.enabled else 'off'})"


class FeatureFlagOverride(TenantModel):
    TARGET_CHOICES = [
        ("workspace", "Workspace"),   # workspace-wide forced value (target_id null)
        ("role", "Role"),             # target_id = Role.id
        ("user", "User"),             # target_id = User.id
    ]

    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name="overrides")
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.UUIDField(null=True, blank=True)  # null for a workspace-wide override
    enabled = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "feature_flag_overrides"
        unique_together = [("workspace_id", "flag", "target_type", "target_id")]
        indexes = [models.Index(fields=["workspace_id", "flag"])]
