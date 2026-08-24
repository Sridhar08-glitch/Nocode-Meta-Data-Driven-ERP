"""
Documents — file attachments, version history, folders, sharing.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentFolder(TenantModel):
    """Hierarchical folder tree per workspace."""
    name = models.CharField(max_length=255)
    parent_id = models.UUIDField(null=True, blank=True, db_index=True)
    path = models.TextField(blank=True)  # materialized path e.g. "/root/hr/2024/"
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "document_folders"
        indexes = [models.Index(fields=["workspace_id", "parent_id"])]


class Document(TenantModel):
    """
    A document record. Actual bytes live in object storage (S3/local).
    Only a storage reference (key/path) is stored here.
    """
    STATUS = [
        ("uploading", "Uploading"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("error", "Error"),
        ("quarantined", "Quarantined"),  # failed AV scan
    ]

    folder_id = models.UUIDField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    mime_type = models.CharField(max_length=127, blank=True)
    extension = models.CharField(max_length=20, blank=True)
    size_bytes = models.BigIntegerField(default=0)

    # Storage reference — NEVER the raw URL, always a signed/resolved key
    storage_key = models.CharField(max_length=1024)
    storage_backend = models.CharField(
        max_length=20, choices=[("local", "Local"), ("s3", "S3")], default="local"
    )
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default="uploading")
    av_scanned_at = models.DateTimeField(null=True, blank=True)
    av_clean = models.BooleanField(null=True, blank=True)

    # Versioning — current active version
    current_version = models.IntegerField(default=1)
    is_latest = models.BooleanField(default=True)

    # Record attachment link (optional)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)
    record_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Tags via tagging app
    is_public = models.BooleanField(default=False)

    class Meta:
        db_table = "documents"
        indexes = [
            models.Index(fields=["workspace_id", "folder_id"]),
            models.Index(fields=["workspace_id", "record_id"]),
        ]


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable version of a document's binary content."""
    document_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    version_number = models.IntegerField()
    storage_key = models.CharField(max_length=1024)
    size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    uploaded_by = models.UUIDField(null=True, blank=True)
    comment = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "document_versions"
        unique_together = [("document_id", "version_number")]


class DocumentShare(UUIDPrimaryKeyMixin, TimestampMixin):
    """Sharing a document with specific members or via public link."""
    SHARE_TYPE = [
        ("member", "Member"),
        ("team", "Team"),
        ("public_link", "Public Link"),
        ("portal_user", "Portal User"),
    ]

    document_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    share_type = models.CharField(max_length=20, choices=SHARE_TYPE)
    recipient_id = models.UUIDField(null=True, blank=True)  # member/team/portal_user id
    permission = models.CharField(
        max_length=10, choices=[("view", "View"), ("comment", "Comment"), ("edit", "Edit")]
    )
    token = models.CharField(max_length=100, blank=True, unique=True)  # for public_link
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "document_shares"
        indexes = [models.Index(fields=["document_id"])]
