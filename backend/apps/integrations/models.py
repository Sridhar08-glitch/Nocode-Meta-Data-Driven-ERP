"""
Integrations — outbound webhook subscriptions, OAuth apps, and HTTP connectors.
No raw secrets stored; only references.
"""
from django.db import models

from apps.core.models import TenantModel, UUIDPrimaryKeyMixin


class WebhookSubscription(TenantModel):
    """
    An outbound webhook: fires on specified domain events.
    """
    STATUS = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("disabled_too_many_errors", "Disabled (Errors)"),
    ]

    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=2000)

    # Secret stored by reference in the secrets store
    signing_secret_ref = models.CharField(max_length=255, blank=True)

    # Which event types to subscribe to (empty = all)
    event_types = models.JSONField(default=list)

    # Optional entity filter
    entity_id = models.UUIDField(null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS, default="active")

    # Delivery settings
    http_method = models.CharField(max_length=10, default="POST")
    headers = models.JSONField(default=dict)   # static headers (no secrets in values)
    timeout_seconds = models.IntegerField(default=30)
    max_retries = models.IntegerField(default=3)

    # Stats
    success_count = models.BigIntegerField(default=0)
    failure_count = models.BigIntegerField(default=0)
    last_fired_at = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)

    class Meta:
        db_table = "webhook_subscriptions"
        indexes = [models.Index(fields=["workspace_id", "status"])]


class WebhookDelivery(UUIDPrimaryKeyMixin):
    """Record of a single webhook delivery attempt."""
    STATUS = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("retrying", "Retrying"),
    ]

    subscription_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    event_id = models.UUIDField(db_index=True)
    event_type = models.CharField(max_length=100)

    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    attempt_number = models.IntegerField(default=1)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    request_headers = models.JSONField(default=dict)
    request_body_hash = models.CharField(max_length=64, blank=True)  # SHA-256, not raw body
    response_status = models.IntegerField(null=True, blank=True)
    response_body_snippet = models.CharField(max_length=500, blank=True)
    duration_ms = models.IntegerField(default=0)

    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "webhook_deliveries"
        indexes = [
            models.Index(fields=["subscription_id", "-delivered_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]


class OAuthApp(TenantModel):
    """
    A third-party OAuth app credential set registered for a workspace.
    CLIENT SECRET IS NEVER STORED HERE — only a reference to the secrets store.
    """
    PROVIDER = [
        ("google", "Google"),
        ("microsoft", "Microsoft"),
        ("slack", "Slack"),
        ("github", "GitHub"),
        ("custom", "Custom OAuth2"),
    ]

    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=30, choices=PROVIDER)
    client_id = models.CharField(max_length=500)
    # Client secret stored only as a reference (e.g. "secrets:workspace:xxx:oauth_google")
    client_secret_ref = models.CharField(max_length=255)
    scopes = models.JSONField(default=list)
    redirect_uri = models.CharField(max_length=2000, blank=True)
    extra_config = models.JSONField(default=dict)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "oauth_apps"
        unique_together = [("workspace_id", "provider", "client_id")]


class HTTPConnector(TenantModel):
    """
    Named HTTP API connector (base URL + auth config) reusable across workflows.
    Auth credentials stored as references only.
    """
    AUTH_TYPE = [
        ("none", "None"),
        ("api_key_header", "API Key (Header)"),
        ("api_key_query", "API Key (Query Param)"),
        ("bearer_token", "Bearer Token"),
        ("basic_auth", "Basic Auth"),
        ("oauth2_client_credentials", "OAuth2 Client Credentials"),
    ]

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    base_url = models.URLField(max_length=2000)
    auth_type = models.CharField(max_length=30, choices=AUTH_TYPE, default="none")
    auth_config = models.JSONField(default=dict)  # {header_name, secret_ref} — no raw values
    default_headers = models.JSONField(default=dict)
    timeout_seconds = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "http_connectors"
        unique_together = [("workspace_id", "slug")]


class InboundWebhook(TenantModel):
    """
    A unique inbound webhook endpoint that triggers workflows.
    Each has a generated token (stored as hash only).
    """
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256 of the token
    workflow_id = models.UUIDField(null=True, blank=True)   # which workflow to trigger
    is_active = models.BooleanField(default=True)

    # Request filtering
    allowed_ips = models.JSONField(default=list)  # CIDR list; empty = any
    expected_content_type = models.CharField(max_length=127, blank=True)

    # Stats
    call_count = models.BigIntegerField(default=0)
    last_called_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inbound_webhooks"
        unique_together = [("workspace_id", "slug")]
