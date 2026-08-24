"""DRF serializers for the backups API (PROJECT_HANDBOOK.md §33.5)."""
from rest_framework import serializers

from .models import BackupJob, DataRetentionPolicy, RestoreJob


class BackupJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupJob
        # storage_key / encryption_key_ref deliberately excluded — never exposed.
        fields = ["id", "backup_type", "status", "initiated_by", "is_automatic",
                  "storage_backend", "size_bytes", "checksum_sha256", "is_encrypted",
                  "entity_count", "record_count", "document_count", "started_at",
                  "completed_at", "expires_at", "error_message", "created_at", "updated_at"]
        read_only_fields = fields


class RestoreJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestoreJob
        # confirmation_token_hash never exposed.
        fields = ["id", "restore_type", "backup_job_id", "pitr_target_sequence",
                  "pitr_target_timestamp", "target_workspace_id", "target_workspace_slug",
                  "status", "initiated_by", "confirmed_at", "started_at", "completed_at",
                  "error_message", "created_at", "updated_at"]
        read_only_fields = fields


class DataRetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = DataRetentionPolicy
        fields = ["id", "entity_id", "entity_slug", "retain_days", "action",
                  "anonymize_fields", "is_active", "last_enforced_at",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "last_enforced_at", "created_at", "updated_at"]
