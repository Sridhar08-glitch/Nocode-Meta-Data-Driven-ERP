"""DRF serializers for the document-templates API."""
from rest_framework import serializers

from .models import DocumentTemplate


class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = ["id", "name", "slug", "entity_slug", "page_config", "blocks",
                  "line_items", "version", "is_active",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "version", "created_by", "created_at", "updated_at"]
