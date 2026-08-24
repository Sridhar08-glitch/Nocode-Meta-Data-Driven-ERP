"""
Per-tenant Backup & Restore — encrypted per-tenant export + PITR metadata.
"""
from django.db import models

from apps.core.models import TenantModel


class BackupJob(TenantModel):
    """
    A per-tenant backup operation (full or incremental).
    """
    BACKUP_TYPE = [
        ("full", "Full"),
        ("incremental", "Incremental"),
        ("config_only", "Config Only"),
    ]
    STATUS = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE, default="full")
    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    initiated_by = models.UUIDField(null=True, blank=True)
    is_automatic = models.BooleanField(default=False)

    # Output
    storage_key = models.CharField(max_length=1024, blank=True)
    storage_backend = models.CharField(max_length=20, default="local")
    size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    # Encryption: key reference (never the key itself)
    encryption_key_ref = models.CharField(max_length=255, blank=True)
    is_encrypted = models.BooleanField(default=True)

    # Coverage
    from_event_sequence = models.BigIntegerField(null=True, blank=True)
    to_event_sequence = models.BigIntegerField(null=True, blank=True)
    entity_count = models.IntegerField(default=0)
    record_count = models.BigIntegerField(default=0)
    document_count = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "backup_jobs"
        indexes = [
            models.Index(fields=["workspace_id", "status"]),
            models.Index(fields=["workspace_id", "-created_at"]),
        ]


class RestoreJob(TenantModel):
    """
    A restore operation.
    ALWAYS targets an isolated workspace (pitr_target_workspace_id),
    NEVER silently overwrites the production workspace.
    """
    STATUS = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    RESTORE_TYPE = [
        ("full_backup", "Full Backup"),
        ("pitr", "Point-in-Time Recovery"),
    ]

    restore_type = models.CharField(max_length=20, choices=RESTORE_TYPE)
    backup_job_id = models.UUIDField(null=True, blank=True)   # for full_backup restore

    # PITR settings
    pitr_target_sequence = models.BigIntegerField(null=True, blank=True)
    pitr_target_timestamp = models.DateTimeField(null=True, blank=True)

    # Target: MUST be a separate workspace (not workspace_id itself)
    target_workspace_id = models.UUIDField()
    target_workspace_slug = models.CharField(max_length=63)

    status = models.CharField(max_length=20, choices=STATUS, default="queued")
    initiated_by = models.UUIDField()

    # Confirmation token: human must supply before restore begins
    confirmation_token_hash = models.CharField(max_length=64, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "restore_jobs"
        indexes = [models.Index(fields=["workspace_id", "-created_at"])]


class DataRetentionPolicy(TenantModel):
    """
    Per-entity data retention rules.
    Celery beat enforces nightly purge of records past their retention window.
    """
    entity_id = models.UUIDField(unique=True, db_index=True)
    entity_slug = models.CharField(max_length=63)

    # Retention period
    retain_days = models.IntegerField(null=True, blank=True)  # null = forever

    # What to do on expiry
    action = models.CharField(
        max_length=20,
        choices=[
            ("soft_delete", "Soft Delete"),
            ("hard_delete", "Hard Delete"),
            ("anonymize", "Anonymize"),
            ("archive", "Archive to Cold Storage"),
        ],
        default="soft_delete",
    )
    # Fields to wipe when anonymizing
    anonymize_fields = models.JSONField(default=list)

    is_active = models.BooleanField(default=True)
    last_enforced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "data_retention_policies"
        indexes = [models.Index(fields=["workspace_id", "is_active"])]
