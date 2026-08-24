"""
Serializers for the CUSTOM admin Portal Builder (workspace owner/admin only).

NOT Django admin — these back the DRF APIViews in ``admin_views.py``. Secrets (password_hash,
mfa_secret) are never exposed; the portal user password is write-only and hashed in the view.
"""
from rest_framework import serializers

from .models import PortalConfiguration, PortalEntityGrant, PortalUser


class PortalConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalConfiguration
        fields = ["id", "is_enabled", "name", "custom_domain", "logo_url", "primary_color",
                  "exposed_entity_ids", "default_role_id", "allow_self_signup",
                  "signup_domain_whitelist", "welcome_message", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class PortalUserSerializer(serializers.ModelSerializer):
    # write-only; hashed in the view, never read back
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, min_length=8)

    class Meta:
        model = PortalUser
        fields = ["id", "email", "full_name", "avatar_url", "is_active", "is_verified",
                  "linked_entity_id", "linked_record_id", "role_id", "portal_type",
                  "last_login_at", "created_at", "updated_at", "password"]
        read_only_fields = ["id", "last_login_at", "created_at", "updated_at"]


class PortalEntityGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalEntityGrant
        fields = ["id", "entity_slug", "portal_type", "link_field", "link_source",
                  "can_read", "can_create", "can_update", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
