from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "actor_id", "actor_type", "actor_name", "action",
            "resource_type", "resource_id", "changed_fields",
            "correlation_id", "event_id", "occurred_at",
        ]
