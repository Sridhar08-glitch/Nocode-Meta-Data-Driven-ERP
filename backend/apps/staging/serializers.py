"""DRF serializers for the import/export API."""
from rest_framework import serializers

from .models import ExportJob, ImportJob, ImportRow


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = ["id", "entity_id", "entity_slug", "initiated_by", "status",
                  "source_filename", "column_mapping", "delimiter", "has_header",
                  "duplicate_strategy", "match_field_slug", "total_rows", "valid_rows",
                  "invalid_rows", "imported_rows", "skipped_rows", "error_rows",
                  "started_at", "completed_at", "error_message", "created_at", "updated_at"]
        read_only_fields = [f for f in fields if f not in
                            ("column_mapping", "duplicate_strategy", "match_field_slug")]


class ImportRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRow
        fields = ["id", "row_number", "raw_data", "mapped_data", "validation_errors",
                  "status", "imported_record_id"]
        read_only_fields = fields


class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportJob
        fields = ["id", "entity_id", "report_id", "initiated_by", "status", "nql_ast",
                  "format", "include_fields", "output_filename", "row_count", "size_bytes",
                  "download_expires_at", "started_at", "completed_at", "error_message",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "initiated_by", "status", "output_filename", "row_count",
                            "size_bytes", "download_expires_at", "started_at", "completed_at",
                            "error_message", "created_at", "updated_at"]
