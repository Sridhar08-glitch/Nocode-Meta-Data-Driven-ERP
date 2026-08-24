"""DRF serializers for the RBAC/ABAC management API (frontend F1.9 Permission Builder)."""
from rest_framework import serializers

from .models import DataMaskingRule, FieldPermission, Permission, Role


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "slug", "description", "is_system", "is_active",
                  "parent_role", "created_at", "updated_at"]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "role", "resource_type", "resource_id", "action", "is_deny",
                  "conditions", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class FieldPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldPermission
        fields = ["id", "field_id", "role_id", "can_read", "can_write",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DataMaskingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataMaskingRule
        fields = ["id", "field_id", "role_id", "mask_type", "mask_pattern",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
