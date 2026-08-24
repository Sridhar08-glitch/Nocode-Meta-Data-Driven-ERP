"""
SLA — Service Level Agreements tracked per record.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class SLAPolicy(TenantModel):
    """
    Defines SLA targets for a specific entity/status combination.
    """
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    entity_id = models.UUIDField(db_index=True)
    description = models.TextField(blank=True)

    # Condition NQL: which records this SLA applies to
    applies_when_nql = models.TextField(blank=True)

    # Targets
    # Each target: {"metric": "first_response"|"resolution"|"custom_field",
    #                "target_minutes": 480, "warning_at_percent": 75,
    #                "business_hours_only": true, "business_hours_id": uuid}
    targets = models.JSONField(default=list)

    # Escalation
    escalation_actions = models.JSONField(default=list)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sla_policies"
        unique_together = [("workspace_id", "slug")]


class BusinessHours(TenantModel):
    """Defines a work-week calendar used by SLA policies."""
    name = models.CharField(max_length=100)
    timezone = models.CharField(max_length=63, default="UTC")

    # {"mon": {"start": "09:00", "end": "17:00"}, "sat": null, ...}
    schedule = models.JSONField(default=dict)
    holidays = models.JSONField(default=list)  # [{"date": "2024-12-25", "name": "Christmas"}]

    # Phase 1.33 — richer calendar (additive; the calculator prefers weekly_hours when set):
    # weekly_hours: per-day LIST of intervals → supports split shifts,
    #   {"mon": [{"start": "09:00", "end": "12:00"}, {"start": "13:00", "end": "17:00"}]}
    weekly_hours = models.JSONField(default=dict)
    # shifts: named reusable patterns, {"morning": [{"start": "06:00", "end": "14:00"}]}
    shifts = models.JSONField(default=dict)
    region = models.CharField(max_length=100, blank=True)  # regional calendar label

    class Meta:
        db_table = "business_hours"


class SLARecord(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Live SLA tracking instance for a single record.
    One row per (record, policy, metric).
    """
    STATUS = [
        ("on_track", "On Track"),
        ("warning", "Warning"),
        ("breached", "Breached"),
        ("met", "Met"),
        ("paused", "Paused"),
    ]

    policy_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()
    record_id = models.UUIDField(db_index=True)
    metric_key = models.CharField(max_length=50)  # first_response / resolution / custom

    status = models.CharField(max_length=20, choices=STATUS, default="on_track")

    started_at = models.DateTimeField()
    target_at = models.DateTimeField()
    warning_at = models.DateTimeField()
    paused_at = models.DateTimeField(null=True, blank=True)
    met_at = models.DateTimeField(null=True, blank=True)
    breached_at = models.DateTimeField(null=True, blank=True)

    # Accumulated pause duration in seconds
    paused_seconds = models.IntegerField(default=0)

    # Escalation tracking
    warning_sent = models.BooleanField(default=False)
    breach_notified = models.BooleanField(default=False)

    class Meta:
        db_table = "sla_records"
        unique_together = [("workspace_id", "record_id", "policy_id", "metric_key")]
        indexes = [
            models.Index(fields=["workspace_id", "status"]),
            models.Index(fields=["target_at"]),
        ]
