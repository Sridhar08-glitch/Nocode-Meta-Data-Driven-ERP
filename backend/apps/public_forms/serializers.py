"""DRF serializers for the public forms API (PROJECT_HANDBOOK.md §33.2)."""
from rest_framework import serializers

from apps.metadata.models import FormDefinition

from .models import FormSubmission


class FormDefinitionSerializer(serializers.ModelSerializer):
    entity_slug = serializers.CharField(source="entity.slug", read_only=True)

    class Meta:
        model = FormDefinition
        fields = ["id", "entity", "entity_slug", "name", "is_default", "is_public",
                  "layout", "settings", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "entity_slug"]


class FormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = ["id", "form_id", "entity_id", "status", "data", "created_record_id",
                  "submitter_name", "submitter_email", "submitter_ip", "honeypot_triggered",
                  "spam_score", "validation_errors", "reviewed_by", "reviewed_at",
                  "rejection_reason", "created_at", "updated_at"]
        read_only_fields = fields
