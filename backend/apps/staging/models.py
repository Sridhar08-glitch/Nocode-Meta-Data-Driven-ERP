"""
Staging / Import — CSV/Excel import pipeline with validation and preview.
"""
from django.db import models

from apps.core.models import TenantModel, UUIDPrimaryKeyMixin


class ImportJob(TenantModel):
    """
    Tracks a data import operation from upload through validation to commit.
    """
    STATUS = [
        ("uploading", "Uploading"),
        ("parsing", "Parsing"),
        ("validating", "Validating"),
        ("awaiting_confirm", "Awaiting Confirmation"),
        ("importing", "Importing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    entity_id = models.UUIDField(db_index=True)
    entity_slug = models.CharField(max_length=63)
    initiated_by = models.UUIDField()

    status = models.CharField(max_length=25, choices=STATUS, default="uploading")

    # Source file
    source_filename = models.CharField(max_length=500)
    source_storage_key = models.CharField(max_length=1024, blank=True)
    source_mime_type = models.CharField(max_length=127, blank=True)

    # Column mapping: {"source_col": "field_slug" | null}
    column_mapping = models.JSONField(default=dict)

    # Parse settings
    delimiter = models.CharField(max_length=5, default=",")
    has_header = models.BooleanField(default=True)
    date_format = models.CharField(max_length=50, default="YYYY-MM-DD")
    encoding = models.CharField(max_length=20, default="utf-8")

    # On duplicate: skip / update / error
    duplicate_strategy = models.CharField(
        max_length=10,
        choices=[("skip", "Skip"), ("update", "Update"), ("error", "Error")],
        default="skip",
    )
    match_field_slug = models.CharField(max_length=100, blank=True)

    # Counts
    total_rows = models.IntegerField(default=0)
    valid_rows = models.IntegerField(default=0)
    invalid_rows = models.IntegerField(default=0)
    imported_rows = models.IntegerField(default=0)
    skipped_rows = models.IntegerField(default=0)
    error_rows = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "import_jobs"
        indexes = [models.Index(fields=["workspace_id", "entity_id", "-created_at"])]


class ImportRow(UUIDPrimaryKeyMixin):
    """
    Staged row from an import job — holds raw + parsed + validation data.
    Rows are written during parsing, read during import, then cleaned up.
    """
    STATUS = [
        ("pending", "Pending"),
        ("valid", "Valid"),
        ("invalid", "Invalid"),
        ("imported", "Imported"),
        ("skipped", "Skipped"),
        ("error", "Error"),
    ]

    job_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    row_number = models.IntegerField()
    raw_data = models.JSONField()              # {"col_A": "raw val", ...}
    mapped_data = models.JSONField(default=dict)  # {"field_slug": typed_val, ...}
    validation_errors = models.JSONField(default=list)  # [{"field", "message"}]
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    imported_record_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "import_rows"
        unique_together = [("job_id", "row_number")]
        indexes = [models.Index(fields=["job_id", "status"])]


class ExportJob(TenantModel):
    """Tracks a data export operation."""
    STATUS = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    entity_id = models.UUIDField(null=True, blank=True)
    report_id = models.UUIDField(null=True, blank=True)
    initiated_by = models.UUIDField()
    status = models.CharField(max_length=15, choices=STATUS, default="queued")

    # NQL AST for the export query
    nql_ast = models.JSONField(null=True, blank=True)

    format = models.CharField(
        max_length=10,
        choices=[("csv", "CSV"), ("xlsx", "Excel"), ("json", "JSON")],
        default="csv",
    )
    include_fields = models.JSONField(default=list)  # field slugs; empty = all

    # Output
    output_storage_key = models.CharField(max_length=1024, blank=True)
    output_filename = models.CharField(max_length=500, blank=True)
    row_count = models.IntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)

    # Link expires
    download_expires_at = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "export_jobs"
        indexes = [models.Index(fields=["workspace_id", "-created_at"])]
