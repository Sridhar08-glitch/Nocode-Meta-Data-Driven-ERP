"""DRF serializers for the integrations API."""
from rest_framework import serializers

from .models import (
    HTTPConnector,
    InboundWebhook,
    OAuthApp,
    WebhookDelivery,
    WebhookSubscription,
)


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ["id", "name", "target_url", "signing_secret_ref", "event_types",
                  "entity_id", "status", "http_method", "headers", "timeout_seconds",
                  "max_retries", "success_count", "failure_count", "last_fired_at",
                  "last_error_at", "consecutive_failures", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "success_count", "failure_count",
                            "last_fired_at", "last_error_at", "consecutive_failures",
                            "created_at", "updated_at"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = ["id", "subscription_id", "event_type", "status", "attempt_number",
                  "next_retry_at", "request_body_hash", "response_status",
                  "response_body_snippet", "duration_ms", "delivered_at", "error_message"]
        read_only_fields = fields


class OAuthAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuthApp
        fields = ["id", "name", "provider", "client_id", "client_secret_ref", "scopes",
                  "redirect_uri", "extra_config", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class HTTPConnectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = HTTPConnector
        fields = ["id", "name", "slug", "base_url", "auth_type", "auth_config",
                  "default_headers", "timeout_seconds", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class InboundWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboundWebhook
        fields = ["id", "name", "slug", "workflow_id", "is_active", "allowed_ips",
                  "expected_content_type", "call_count", "last_called_at",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "call_count", "last_called_at", "created_at", "updated_at"]
