"""DRF serializers for the email-templates API."""
from rest_framework import serializers

from .models import EmailTemplate


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "name", "slug", "locale", "subject_template", "body_html",
                  "blocks", "variables", "version", "is_active",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "version", "created_by", "created_at", "updated_at"]
