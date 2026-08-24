"""
Audit Log — immutable compliance record of every state-changing API call.
Complements the event store; written by middleware for every mutating request.
"""
from django.db import models

from apps.core.models import UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin):
    """
    Append-only record of every mutating API call.
    Never updated after creation. Hard-delete prohibited at DB level (trigger).
    """
    workspace_id = models.UUIDField(db_index=True)

    # Actor
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_type = models.CharField(
        max_length=20,
        choices=[
            ("user", "User"),
            ("api_key", "API Key"),
            ("system", "System"),
            ("workflow", "Workflow"),
            ("portal_user", "Portal User"),
        ],
        default="user",
    )
    actor_name = models.CharField(max_length=255, blank=True)  # snapshot at log time
    actor_ip = models.GenericIPAddressField(null=True, blank=True)
    actor_user_agent = models.CharField(max_length=500, blank=True)

    # HTTP request
    http_method = models.CharField(max_length=10)
    http_path = models.CharField(max_length=2000)
    http_status = models.IntegerField()
    request_id = models.CharField(max_length=100, blank=True, db_index=True)

    # Resource
    resource_type = models.CharField(max_length=50, blank=True)
    resource_id = models.CharField(max_length=100, blank=True, db_index=True)

    # Action
    action = models.CharField(max_length=50)
    description = models.CharField(max_length=500, blank=True)

    # Payload summary (never store full PII; only field names)
    changed_fields = models.JSONField(default=list)

    # Source
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True)
    event_id = models.UUIDField(null=True, blank=True)

    occurred_at = models.DateTimeField(db_index=True)
    duration_ms = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        # Immutable: allow the initial insert (UUID pk is set by default at init),
        # block any update of an already-persisted row.
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("AuditLog records are immutable.")
        super().save(*args, **kwargs)

    class Meta:
        db_table = "audit_logs"
        indexes = [
            models.Index(fields=["workspace_id", "-occurred_at"]),
            models.Index(fields=["workspace_id", "actor_id", "-occurred_at"]),
            models.Index(fields=["workspace_id", "resource_type", "resource_id"]),
        ]
