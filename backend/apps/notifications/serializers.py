"""DRF serializers for the notifications API."""
from rest_framework import serializers

from .models import Notification, NotificationPreference, NotificationTemplate


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "template_id", "recipient_id", "recipient_type", "channel",
                  "status", "subject", "body", "action_url", "entity_id", "record_id",
                  "group_key", "actor_id", "sent_at", "read_at", "failed_reason",
                  "created_at"]
        read_only_fields = fields


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "slug", "name", "channel", "subject_template",
                  "body_template", "is_system", "created_at", "updated_at"]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "event_type", "channel", "enabled", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
