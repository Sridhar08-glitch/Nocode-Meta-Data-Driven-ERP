"""
Serializers specific to the public Metadata API.

Entity/field create + output shapes are reused from ``schema_registry.serializers``
to avoid duplication; this module only adds the metadata-only operations.
"""
from rest_framework import serializers

from .models import FormDefinition, Module


class ModuleSerializer(serializers.ModelSerializer):
    """Top-level grouping (CRM, HRMS, …) the metadata-driven sidebar groups entities under."""

    class Meta:
        model = Module
        fields = ["id", "name", "slug", "description", "icon", "color", "is_system",
                  "is_active", "order", "settings", "created_at", "updated_at"]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]


class EntityUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    plural_name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    title_field_slug = serializers.CharField(required=False)
    settings = serializers.DictField(required=False)
    is_active = serializers.BooleanField(required=False)
    icon = serializers.CharField(required=False, allow_blank=True)
    color = serializers.CharField(required=False, allow_blank=True)


class FieldSlugSerializer(serializers.Serializer):
    field_slug = serializers.SlugField()


# ── Form Builder (Phase 1.26) ────────────────────────────────────────────────
class FormDefinitionOutputSerializer(serializers.ModelSerializer):
    entity_slug = serializers.CharField(source="entity.slug", read_only=True)

    class Meta:
        model = FormDefinition
        fields = ["id", "entity", "entity_slug", "name", "is_default", "is_public",
                  "layout", "settings", "created_by", "created_at", "updated_at"]
        read_only_fields = fields


class FormCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    is_default = serializers.BooleanField(required=False, default=False)
    is_public = serializers.BooleanField(required=False, default=False)
    layout = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    settings = serializers.DictField(required=False, default=dict)


class FormUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    is_default = serializers.BooleanField(required=False)
    is_public = serializers.BooleanField(required=False)
    layout = serializers.ListField(child=serializers.DictField(), required=False)
    settings = serializers.DictField(required=False)
