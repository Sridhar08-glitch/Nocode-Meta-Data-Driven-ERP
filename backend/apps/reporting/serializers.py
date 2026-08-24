"""DRF serializers for the reporting API."""
from rest_framework import serializers

from .models import Dashboard, DashboardWidget, Report, ReportSnapshot


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "name", "slug", "description", "report_type", "nql_ast",
                  "nql_source", "display_config", "source_entity_ids", "schedule_cron",
                  "schedule_recipients", "last_run_at", "is_public", "shared_with",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "last_run_at", "created_at", "updated_at"]


class ReportSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSnapshot
        fields = ["id", "report_id", "row_count", "data", "generated_by",
                  "duration_ms", "created_at"]
        read_only_fields = fields


class ReportSnapshotListSerializer(serializers.ModelSerializer):
    """Snapshot metadata without the (potentially large) data payload."""
    class Meta:
        model = ReportSnapshot
        fields = ["id", "report_id", "row_count", "generated_by", "duration_ms", "created_at"]
        read_only_fields = fields


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = ["id", "dashboard_id", "widget_type", "title", "report_id",
                  "grid_x", "grid_y", "grid_w", "grid_h", "config",
                  "refresh_interval_seconds", "source_report_ids", "created_at", "updated_at"]
        read_only_fields = ["id", "dashboard_id", "created_at", "updated_at"]


class DashboardSerializer(serializers.ModelSerializer):
    widgets = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = ["id", "name", "slug", "description", "layout", "is_public",
                  "is_default", "shared_with", "widgets", "created_at", "updated_at"]
        read_only_fields = ["id", "widgets", "created_at", "updated_at"]

    def get_widgets(self, obj):
        qs = DashboardWidget.objects.filter(
            dashboard_id=obj.id, workspace_id=obj.workspace_id).order_by("grid_y", "grid_x")
        return DashboardWidgetSerializer(qs, many=True).data
