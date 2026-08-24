"""DRF serializers for the SLA API."""
from rest_framework import serializers

from .models import BusinessHours, SLAPolicy, SLARecord


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = ["id", "name", "slug", "entity_id", "description", "applies_when_nql",
                  "targets", "escalation_actions", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = ["id", "name", "timezone", "schedule", "holidays",
                  "weekly_hours", "shifts", "region", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SLARecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SLARecord
        fields = ["id", "policy_id", "entity_id", "record_id", "metric_key", "status",
                  "started_at", "target_at", "warning_at", "paused_at", "met_at",
                  "breached_at", "paused_seconds", "warning_sent", "breach_notified"]
        read_only_fields = fields
