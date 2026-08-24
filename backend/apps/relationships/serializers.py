"""Serializers for the relationship builder API."""
from rest_framework import serializers

from .models import RelationshipDefinition


class RelationshipCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.SlugField()
    source_entity_id = serializers.UUIDField()
    target_entity_id = serializers.UUIDField()
    cardinality = serializers.ChoiceField(
        choices=[c[0] for c in RelationshipDefinition.CARDINALITY])
    on_delete = serializers.ChoiceField(
        choices=["protect", "cascade", "set_null", "detach"], default="detach")
    source_field_slug = serializers.SlugField(required=False, allow_blank=True)


class RelationshipOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationshipDefinition
        fields = [
            "id", "name", "slug", "source_entity_id", "target_entity_id",
            "cardinality", "on_delete", "source_field_slug", "target_field_slug",
            "junction_table", "is_system", "created_at",
        ]


class LinkSerializer(serializers.Serializer):
    source_record_id = serializers.UUIDField()
    target_record_id = serializers.UUIDField()
