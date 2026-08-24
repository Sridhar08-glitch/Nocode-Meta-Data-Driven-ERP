"""
Approvals — multi-level approval gates embedded in workflows or standalone.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class ApprovalProcess(TenantModel):
    """
    Template defining the sequence of approval levels for a given entity/action.
    """
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    entity_id = models.UUIDField(db_index=True)
    trigger_condition_nql = models.TextField(blank=True)  # when to invoke

    # Ordered levels
    # Each level: {"level": 1, "approvers": [{type: "role"|"member"|"field", value: "..."}],
    #               "quorum": "any"|"all", "timeout_hours": 24, "on_timeout": "escalate"|"reject"|"auto_approve"}
    levels = models.JSONField(default=list)

    # Actions on final decision
    on_approve_actions = models.JSONField(default=list)
    on_reject_actions = models.JSONField(default=list)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "approval_processes"
        unique_together = [("workspace_id", "slug")]


class ApprovalRequest(TenantModel):
    """
    A single approval request instance for a record.
    """
    STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    process_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()
    record_id = models.UUIDField(db_index=True)

    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    current_level = models.IntegerField(default=1)

    requested_by = models.UUIDField()
    resolved_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_comment = models.TextField(blank=True)

    # The workflow_run that spawned this request (if any)
    workflow_run_id = models.UUIDField(null=True, blank=True)
    step_run_id = models.UUIDField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "approval_requests"
        indexes = [
            models.Index(fields=["workspace_id", "record_id"]),
            models.Index(fields=["workspace_id", "status"]),
        ]


class ApprovalDecision(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single approver's vote on an approval request.
    """
    request_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField()
    level = models.IntegerField()
    approver_id = models.UUIDField()  # WorkspaceMember.id
    decision = models.CharField(
        max_length=10, choices=[("approve", "Approve"), ("reject", "Reject")]
    )
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval_decisions"
        unique_together = [("request_id", "level", "approver_id")]
        indexes = [models.Index(fields=["request_id", "level"])]
