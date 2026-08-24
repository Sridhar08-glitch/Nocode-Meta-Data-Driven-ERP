"""DRF serializers for the feature-flags API."""
from rest_framework import serializers

from .models import FeatureFlag, FeatureFlagOverride


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["id", "key", "name", "description", "enabled", "rollout_percent",
                  "scope", "config", "is_active", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_rollout_percent(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("rollout_percent must be between 0 and 100.")
        return value


class FeatureFlagOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlagOverride
        fields = ["id", "flag", "target_type", "target_id", "enabled",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "flag", "created_by", "created_at", "updated_at"]

    def validate(self, data):
        if data.get("target_type") in ("role", "user") and not data.get("target_id"):
            raise serializers.ValidationError("target_id is required for role/user overrides.")
        if data.get("target_type") == "workspace" and data.get("target_id"):
            raise serializers.ValidationError("workspace overrides must not set target_id.")
        return data
