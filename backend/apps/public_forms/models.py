"""
Public Forms — shareable form submissions for external data collection.
FormDefinition lives in apps/metadata.
This module handles submissions.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class FormSubmission(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single form submission from an external (portal or anonymous) user.
    """
    STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("spam", "Spam"),
    ]

    form_id = models.UUIDField(db_index=True)      # FormDefinition.id
    workspace_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()

    status = models.CharField(max_length=15, choices=STATUS, default="pending")

    # Submitted data (field_slug → raw submitted value)
    data = models.JSONField()

    # Resulting record (created after validation)
    created_record_id = models.UUIDField(null=True, blank=True)

    # Submitter info (for anonymous submissions)
    submitter_name = models.CharField(max_length=255, blank=True)
    submitter_email = models.EmailField(blank=True)
    submitter_ip = models.GenericIPAddressField(null=True, blank=True)
    submitter_user_agent = models.CharField(max_length=500, blank=True)

    # For portal user submissions
    portal_user_id = models.UUIDField(null=True, blank=True)

    # Spam / honeypot
    honeypot_triggered = models.BooleanField(default=False)
    spam_score = models.FloatField(default=0.0)

    validation_errors = models.JSONField(default=list)
    reviewed_by = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "form_submissions"
        indexes = [
            models.Index(fields=["workspace_id", "form_id", "-created_at"]),
            models.Index(fields=["workspace_id", "status"]),
        ]
