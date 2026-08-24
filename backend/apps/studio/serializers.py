"""DRF serializers for the Studio API."""
from rest_framework import serializers

from .models import Application, HomeLayout, Navigation


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["id", "name", "slug", "description", "icon", "color",
                  "included_entity_ids", "navigation_id", "home_layout_id", "role_ids",
                  "theme_overrides", "order", "is_published", "is_active",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "is_published", "created_by", "created_at", "updated_at"]


class HomeLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeLayout
        fields = ["id", "name", "scope", "target_id", "widgets", "is_published",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "is_published", "created_by", "created_at", "updated_at"]

    def validate(self, data):
        scope = data.get("scope", getattr(self.instance, "scope", "workspace"))
        target = data.get("target_id", getattr(self.instance, "target_id", None))
        if scope == "workspace" and target:
            raise serializers.ValidationError("workspace-scope layout must not set target_id.")
        if scope in ("app", "role", "personal") and not target:
            raise serializers.ValidationError(f"{scope}-scope layout requires target_id.")
        return data


class NavigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Navigation
        fields = ["id", "name", "scope", "target_id", "tree", "is_published",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "is_published", "created_by", "created_at", "updated_at"]

    def validate(self, data):
        scope = data.get("scope", getattr(self.instance, "scope", "workspace"))
        target = data.get("target_id", getattr(self.instance, "target_id", None))
        if scope == "workspace" and target:
            raise serializers.ValidationError("workspace-scope navigation must not set target_id.")
        if scope in ("app", "role") and not target:
            raise serializers.ValidationError(f"{scope}-scope navigation requires target_id.")
        return data
