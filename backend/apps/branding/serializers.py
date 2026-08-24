"""DRF serializers for the branding API."""
from rest_framework import serializers

from .models import EmailSMTPConfig, WorkspaceBranding


class WorkspaceBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceBranding
        exclude = ["workspace_id", "deleted_at", "deleted_by", "created_by", "updated_by"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmailSMTPConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSMTPConfig
        fields = ["id", "host", "port", "username", "password_ref", "use_tls", "use_ssl",
                  "from_email", "from_name", "is_verified", "verified_at", "last_test_at",
                  "last_test_result", "created_at", "updated_at"]
        read_only_fields = ["id", "is_verified", "verified_at", "last_test_at",
                            "last_test_result", "created_at", "updated_at"]
