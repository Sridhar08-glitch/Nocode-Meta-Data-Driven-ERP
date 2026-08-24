"""
Schema Registry — DRF Serializers
==================================

Input  serializers: validate inbound data (creation / updates).
Output serializers: represent entity, field, and schema-version responses.

No AI, no async, no stubs.
"""
from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

from apps.metadata.models import (
    FIELD_TYPE_CHOICES,
    EntityDefinition,
    FieldDefinition,
    SchemaVersion,
)

_SLUG_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _slug_validator(value: str) -> None:
    if not _SLUG_RE.match(value):
        raise serializers.ValidationError(
            "Slug must start with a lowercase letter and contain only "
            "lowercase letters, digits, or underscores (max 63 chars)."
        )


# ---------------------------------------------------------------------------
# Field-spec serializer (used inline when creating/patching entity fields)
# ---------------------------------------------------------------------------

class FieldSpecSerializer(serializers.Serializer):
    """Validates a single field specification dict."""

    slug = serializers.SlugField(max_length=63, validators=[_slug_validator])
    name = serializers.CharField(max_length=100)
    field_type = serializers.ChoiceField(choices=FIELD_TYPE_CHOICES)
    description = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
    is_promoted = serializers.BooleanField(required=False, default=False)
    is_filterable = serializers.BooleanField(required=False, default=True)
    is_sortable = serializers.BooleanField(required=False, default=True)
    is_searchable = serializers.BooleanField(required=False, default=False)
    has_index = serializers.BooleanField(required=False, default=False)
    is_required = serializers.BooleanField(required=False, default=False)
    is_unique = serializers.BooleanField(required=False, default=False)
    default_value = serializers.JSONField(required=False, default=None, allow_null=True)
    config = serializers.JSONField(required=False, default=dict)
    order = serializers.IntegerField(required=False, default=0)
    read_roles = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    write_roles = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    def validate_config(self, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("config must be a JSON object.")
        return value


# ---------------------------------------------------------------------------
# Create entity
# ---------------------------------------------------------------------------

class CreateEntitySerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=63, validators=[_slug_validator])
    name = serializers.CharField(max_length=100)
    plural_name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
    title_field_slug = serializers.CharField(max_length=63, required=False, default="name")
    settings = serializers.JSONField(required=False, default=dict)
    fields = FieldSpecSerializer(many=True, required=False, default=list)

    def validate_fields(self, value: list) -> list:
        slugs = [f["slug"] for f in value]
        if len(slugs) != len(set(slugs)):
            raise serializers.ValidationError("Duplicate field slugs in fields list.")
        return value

    def validate_settings(self, value: Any) -> Any:
        if not isinstance(value, dict):
            raise serializers.ValidationError("settings must be a JSON object.")
        return value


# ---------------------------------------------------------------------------
# Add / Update field
# ---------------------------------------------------------------------------

class AddFieldSerializer(FieldSpecSerializer):
    """Extends FieldSpecSerializer — no extra fields needed for add."""
    pass


class UpdateFieldSerializer(serializers.Serializer):
    """Partial update — all fields optional."""
    name = serializers.CharField(max_length=100, required=False)
    field_type = serializers.ChoiceField(choices=FIELD_TYPE_CHOICES, required=False)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_promoted = serializers.BooleanField(required=False)
    is_filterable = serializers.BooleanField(required=False)
    is_sortable = serializers.BooleanField(required=False)
    is_searchable = serializers.BooleanField(required=False)
    has_index = serializers.BooleanField(required=False)
    is_required = serializers.BooleanField(required=False)
    is_unique = serializers.BooleanField(required=False)
    default_value = serializers.JSONField(required=False, allow_null=True)
    config = serializers.JSONField(required=False)
    order = serializers.IntegerField(required=False)
    is_hidden = serializers.BooleanField(required=False)
    is_readonly = serializers.BooleanField(required=False)
    read_roles = serializers.ListField(child=serializers.CharField(), required=False)
    write_roles = serializers.ListField(child=serializers.CharField(), required=False)


# ---------------------------------------------------------------------------
# Output serializers
# ---------------------------------------------------------------------------

class FieldDefinitionOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldDefinition
        fields = [
            "id", "slug", "name", "field_type", "description",
            "is_promoted", "column_name",
            "is_filterable", "is_sortable", "is_searchable", "has_index",
            "is_required", "is_unique", "default_value",
            "is_system", "is_hidden", "is_readonly",
            "order", "config", "read_roles", "write_roles",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class EntityDefinitionOutputSerializer(serializers.ModelSerializer):
    fields = FieldDefinitionOutputSerializer(many=True, read_only=True)

    class Meta:
        model = EntityDefinition
        fields = [
            "id", "workspace_id", "slug", "name", "plural_name",
            "description", "table_name", "has_physical_table",
            "current_schema_version", "title_field_slug", "module",
            "icon", "color",
            "is_system", "is_active", "settings",
            "fields", "created_at", "updated_at",
        ]
        read_only_fields = fields


class SchemaVersionOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemaVersion
        fields = [
            "id", "version", "snapshot", "migration_sql",
            "applied_at", "applied_by", "is_current", "parent_version",
        ]
        read_only_fields = fields


class DiffVersionsSerializer(serializers.Serializer):
    """Input for diff_versions endpoint."""
    version_a = serializers.IntegerField(min_value=1)
    version_b = serializers.IntegerField(min_value=1)

    def validate(self, data: dict) -> dict:
        if data["version_a"] == data["version_b"]:
            raise serializers.ValidationError("version_a and version_b must be different.")
        return data


class RollbackSerializer(serializers.Serializer):
    """Input for rollback endpoint."""
    target_version = serializers.IntegerField(min_value=1)
