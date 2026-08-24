"""DRF serializers for the Numbering Engine API (Phase P2.1)."""
from rest_framework import serializers

from .models import NumberAllocation, NumberSequence


class NumberSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberSequence
        fields = [
            "id", "key", "name", "description", "prefix", "suffix", "padding",
            "start_value", "increment", "reset_scope", "include_period_in_format",
            "current_value", "period_key", "is_active", "is_system",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "current_value", "period_key", "is_system",
                            "created_by", "created_at", "updated_at"]


class NumberAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberAllocation
        fields = ["id", "sequence", "key", "formatted", "value", "period_key",
                  "context", "allocated_by", "created_at"]
        read_only_fields = fields
