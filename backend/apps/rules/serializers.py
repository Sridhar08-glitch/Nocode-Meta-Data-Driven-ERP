"""DRF serializers for the Business Rules management API (frontend F2.4)."""
from rest_framework import serializers

from .models import BusinessRule


class BusinessRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessRule
        fields = [
            "id", "name", "slug", "description", "entity_id", "trigger_on",
            "watch_field_slug", "condition_nql", "actions", "priority", "run_all",
            "is_active", "is_system", "eval_count", "match_count", "last_matched_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "is_system", "eval_count", "match_count", "last_matched_at",
            "created_at", "updated_at",
        ]
