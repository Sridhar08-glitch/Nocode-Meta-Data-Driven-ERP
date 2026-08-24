"""
Workflows — multi-step process automation (Processes).
Business Rules Engine (immediate decisions) lives in apps/rules/.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowDefinition(TenantModel):
    """
    A workflow template: trigger + ordered list of steps + branching.
    """
    TRIGGER_TYPES = [
        ("record_created", "Record Created"),
        ("record_updated", "Record Updated"),
        ("record_deleted", "Record Deleted"),
        ("field_changed", "Field Changed"),
        ("schedule", "Scheduled (CRON)"),
        ("webhook", "Incoming Webhook"),
        ("manual", "Manual / Button"),
        ("stage_entered", "Stage Entered"),
        ("sla_breached", "SLA Breached"),
        ("form_submitted", "Form Submitted"),
    ]
    STATUS = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    trigger_type = models.CharField(max_length=50, choices=TRIGGER_TYPES)
    trigger_config = models.JSONField(default=dict)  # entity_id, field slugs, cron expr, etc.

    entity_id = models.UUIDField(null=True, blank=True, db_index=True)  # scoped entity
    module_id = models.UUIDField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    version = models.IntegerField(default=1)
    is_system = models.BooleanField(default=False)

    # Concurrency / error settings
    max_concurrent_runs = models.IntegerField(default=10)
    timeout_seconds = models.IntegerField(default=3600)
    retry_policy = models.JSONField(default=dict)  # max_retries, backoff

    # Stats (denormalized)
    run_count = models.BigIntegerField(default=0)
    error_count = models.BigIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_definitions"
        unique_together = [("workspace_id", "slug")]


class WorkflowStep(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single action node in a workflow graph.
    """
    STEP_TYPES = [
        ("action_update_record", "Update Record"),
        ("action_create_record", "Create Record"),
        ("action_delete_record", "Delete Record"),
        ("action_send_email", "Send Email"),
        ("action_send_notification", "Send In-App Notification"),
        ("action_send_webhook", "Send Webhook"),
        ("action_call_api", "HTTP API Call"),
        ("action_run_workflow", "Run Sub-Workflow"),
        ("action_run_script", "Run Server Script"),
        ("action_assign", "Assign Record"),
        ("action_add_tag", "Add Tag"),
        ("action_post_journal", "Post Journal Entry"),
        ("action_generate_document", "Generate Document"),
        ("action_wait", "Wait / Delay"),
        ("condition", "Condition (Branch)"),
        ("approval", "Approval Gate"),
        ("loop", "Loop"),
        ("parallel", "Parallel Split"),
        ("join", "Join / Merge"),
    ]

    workflow_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    step_type = models.CharField(max_length=50, choices=STEP_TYPES)
    name = models.CharField(max_length=255)
    config = models.JSONField(default=dict)  # step-specific configuration

    # Graph position
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)

    # Execution order / edges stored in WorkflowEdge
    is_entry = models.BooleanField(default=False)

    # Error handling per step
    on_error = models.CharField(
        max_length=20,
        choices=[("stop", "Stop"), ("continue", "Continue"), ("retry", "Retry")],
        default="stop",
    )
    retry_config = models.JSONField(default=dict)

    class Meta:
        db_table = "workflow_steps"
        indexes = [models.Index(fields=["workflow_id"])]


class WorkflowEdge(UUIDPrimaryKeyMixin):
    """Directed edge between two steps (with optional condition label)."""
    workflow_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField()
    source_step_id = models.UUIDField(db_index=True)
    target_step_id = models.UUIDField(db_index=True)
    condition_label = models.CharField(max_length=50, blank=True)  # "true"/"false"/"default"
    condition_expr = models.TextField(blank=True)  # NQL filter expression

    class Meta:
        db_table = "workflow_edges"
        indexes = [models.Index(fields=["workflow_id"])]


class WorkflowRun(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single execution instance of a workflow definition.
    """
    STATUS = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("timed_out", "Timed Out"),
    ]

    workflow_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)

    trigger_type = models.CharField(max_length=50)
    trigger_payload = models.JSONField(default=dict)

    # Context record
    entity_id = models.UUIDField(null=True, blank=True)
    record_id = models.UUIDField(null=True, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    error_message = models.TextField(blank=True)
    error_step_id = models.UUIDField(null=True, blank=True)

    # Run-time variables / context
    context = models.JSONField(default=dict)

    initiated_by = models.UUIDField(null=True, blank=True)  # actor

    class Meta:
        db_table = "workflow_runs"
        indexes = [
            models.Index(fields=["workspace_id", "workflow_id"]),
            models.Index(fields=["workspace_id", "record_id"]),
            models.Index(fields=["status", "started_at"]),
        ]


class WorkflowStepRun(UUIDPrimaryKeyMixin):
    """Execution record for a single step within a workflow run."""
    STATUS = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
        ("waiting_approval", "Waiting Approval"),
    ]

    run_id = models.UUIDField(db_index=True)
    step_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField()

    status = models.CharField(max_length=25, choices=STATUS, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    attempt_number = models.IntegerField(default=1)

    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "workflow_step_runs"
        indexes = [models.Index(fields=["run_id"])]
