"""
Environment Promotion models (Phase P2.15).

Release management + configuration transport — ORCHESTRATION over the existing Config VCS (1.28
branch/merge/commit/rollback) and the P2.14 dependency precheck. Environments map to Config VCS
branches (DEV/TEST/UAT/PROD); a promotion package captures the objects + diff + risk for moving
config between two environments; approvals enforce segregation of duties. NO new VCS / metadata /
dependency / rollback engine is created. Workspace-scoped (TenantModel) + RLS (migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel


class Environment(TenantModel):
    name = models.CharField(max_length=80)
    env_type = models.CharField(max_length=10, default="dev")   # dev | test | uat | prod
    branch = models.CharField(max_length=100)                   # the Config VCS branch name
    sequence = models.IntegerField(default=0)                   # promotion order dev<test<uat<prod
    is_production = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="active")

    class Meta:
        db_table = "promotion_environments"
        unique_together = [("workspace_id", "env_type")]
        indexes = [models.Index(fields=["workspace_id", "sequence"])]


class PromotionPackage(TenantModel):
    name = models.CharField(max_length=150)
    version = models.CharField(max_length=20, default="1")
    source_env_id = models.UUIDField(db_index=True)
    target_env_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20, default="draft")
    # draft | precheck | approved | executed | failed | rolled_back | cancelled
    object_refs = models.JSONField(default=list)    # [{object_type, object_id}]
    diff = models.JSONField(default=dict)           # Config-VCS diff (source vs target)
    risk_summary = models.JSONField(default=dict)   # {low, medium, high, critical, blocked}
    precheck = models.JSONField(default=dict)       # dependency precheck output
    package_hash = models.CharField(max_length=64, blank=True)   # integrity (Module 15)
    source_sha = models.CharField(max_length=64, blank=True)
    target_sha_before = models.CharField(max_length=64, blank=True)  # rollback point (Module 11)
    merge_commit_sha = models.CharField(max_length=64, blank=True)
    created_by = models.UUIDField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    executed_by = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "promotion_packages"
        indexes = [models.Index(fields=["workspace_id", "status"]),
                   models.Index(fields=["workspace_id", "target_env_id", "status"])]


class PromotionApproval(TenantModel):
    package_id = models.UUIDField(db_index=True)
    role = models.CharField(max_length=30, default="approver")   # reviewer|approver|release_manager
    approver_id = models.UUIDField(null=True, blank=True)
    decision = models.CharField(max_length=20, default="approved")  # approved|rejected
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "promotion_approvals"
        indexes = [models.Index(fields=["workspace_id", "package_id"])]
