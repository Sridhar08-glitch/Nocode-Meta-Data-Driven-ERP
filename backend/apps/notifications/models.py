"""
Notifications — in-app, email, push channels + WebSocket delivery.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin):
    """Reusable notification templates with Jinja-safe variable slots."""
    workspace_id = models.UUIDField(db_index=True)
    slug = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    channel = models.CharField(
        max_length=20,
        choices=[
            ("in_app", "In-App"),
            ("email", "Email"),
            ("push", "Push"),
            ("sms", "SMS"),
            ("webhook", "Webhook"),
        ],
    )
    subject_template = models.CharField(max_length=500, blank=True)
    body_template = models.TextField()  # safe template — no code execution
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "notification_templates"
        unique_together = [("workspace_id", "slug", "channel")]


class Notification(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single notification instance sent to a specific recipient.
    """
    CHANNEL = [
        ("in_app", "In-App"),
        ("email", "Email"),
        ("push", "Push"),
        ("sms", "SMS"),
    ]
    STATUS = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("read", "Read"),
    ]

    workspace_id = models.UUIDField(db_index=True)
    template_id = models.UUIDField(null=True, blank=True)

    # Recipient (workspace member or portal user)
    recipient_id = models.UUIDField(db_index=True)
    recipient_type = models.CharField(
        max_length=20,
        choices=[("member", "Member"), ("portal_user", "Portal User")],
        default="member",
    )

    channel = models.CharField(max_length=20, choices=CHANNEL, default="in_app")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")

    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()

    # Context / deep link
    action_url = models.CharField(max_length=2000, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    record_id = models.UUIDField(null=True, blank=True)

    # Grouping / stacking
    group_key = models.CharField(max_length=255, blank=True, db_index=True)
    actor_id = models.UUIDField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True)

    # Dedup
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(fields=["workspace_id", "recipient_id", "status"]),
            models.Index(fields=["workspace_id", "recipient_id", "read_at"]),
        ]


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-member channel and event-type preferences."""
    workspace_id = models.UUIDField(db_index=True)
    member_id = models.UUIDField(db_index=True)  # WorkspaceMember
    event_type = models.CharField(max_length=100)  # e.g. "record_assigned"
    channel = models.CharField(max_length=20)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_preferences"
        unique_together = [("workspace_id", "member_id", "event_type", "channel")]


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin):
    """Web Push (VAPID) or FCM token for a user's browser/device."""
    workspace_id = models.UUIDField()
    member_id = models.UUIDField(db_index=True)
    endpoint = models.TextField()
    # Keys stored as references — actual p256dh/auth stored encrypted in secrets store
    keys_ref = models.CharField(max_length=255, blank=True)
    device_label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "push_subscriptions"
        indexes = [models.Index(fields=["member_id", "is_active"])]
