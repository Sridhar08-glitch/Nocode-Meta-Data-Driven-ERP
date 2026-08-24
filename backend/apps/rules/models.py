"""
Business Rules Engine — immediate decisions triggered on record change.
Distinct from Workflows (multi-step processes).
Decision: IF <conditions> THEN <actions> executed synchronously.
"""
from django.db import models

from apps.core.models import TenantModel, UUIDPrimaryKeyMixin


class BusinessRule(TenantModel):
    """
    A single if/then rule evaluated when a record is saved.
    Rules are evaluated in priority order; first match wins (unless run_all=True).
    """
    TRIGGER_ON = [
        ("before_create", "Before Create"),
        ("after_create", "After Create"),
        ("before_update", "Before Update"),
        ("after_update", "After Update"),
        ("before_delete", "Before Delete"),
        ("after_delete", "After Delete"),
        ("field_changed", "Specific Field Changed"),
    ]

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    entity_id = models.UUIDField(db_index=True)
    trigger_on = models.CharField(max_length=25, choices=TRIGGER_ON)

    # Field slug that, when changed, fires the rule (for field_changed trigger)
    watch_field_slug = models.CharField(max_length=100, blank=True)

    # Condition: NQL filter expression evaluated against the record
    condition_nql = models.TextField(blank=True)  # empty = always fire

    # Actions: ordered list of action configs
    actions = models.JSONField(default=list)
    # e.g. [{"type": "set_field", "field": "status", "value": "approved"},
    #        {"type": "send_notification", "template_slug": "...", "to": "owner"}]

    # Evaluation order
    priority = models.IntegerField(default=100)
    run_all = models.BooleanField(default=True)  # continue to lower-priority rules?

    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    # Stats
    eval_count = models.BigIntegerField(default=0)
    match_count = models.BigIntegerField(default=0)
    last_matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "business_rules"
        unique_together = [("workspace_id", "slug")]
        indexes = [
            models.Index(fields=["workspace_id", "entity_id", "is_active", "priority"]),
        ]


class RuleExecutionLog(UUIDPrimaryKeyMixin):
    """Audit log of each rule evaluation."""
    rule_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    record_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()
    trigger_on = models.CharField(max_length=25)
    condition_matched = models.BooleanField()
    actions_executed = models.JSONField(default=list)
    error_message = models.TextField(blank=True)
    duration_ms = models.IntegerField(default=0)
    executed_at = models.DateTimeField(auto_now_add=True)
    actor_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "rule_execution_logs"
        indexes = [
            models.Index(fields=["rule_id", "-executed_at"]),
            models.Index(fields=["workspace_id", "record_id"]),
        ]
