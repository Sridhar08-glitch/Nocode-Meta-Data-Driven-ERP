"""
Reporting — saved NQL queries, dashboards, widgets, scheduled reports.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class Report(TenantModel):
    """
    A saved NQL query with display configuration.
    Source of truth for any tabular / chart / pivot view.
    """
    REPORT_TYPE = [
        ("table", "Table"),
        ("chart", "Chart"),
        ("pivot", "Pivot Table"),
        ("funnel", "Funnel"),
        ("cohort", "Cohort"),
        ("kanban_summary", "Kanban Summary"),
        ("timeline", "Timeline"),
    ]

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=25, choices=REPORT_TYPE, default="table")

    # NQL AST stored as JSON
    nql_ast = models.JSONField()

    # Raw NQL string (for display/edit)
    nql_source = models.TextField(blank=True)

    # Display config (chart type, axis mapping, colour palette, etc.)
    display_config = models.JSONField(default=dict)

    # Data lineage: which entity definitions contribute to this report
    source_entity_ids = models.JSONField(default=list)

    # Scheduling
    schedule_cron = models.CharField(max_length=100, blank=True)
    schedule_recipients = models.JSONField(default=list)  # member UUIDs
    last_run_at = models.DateTimeField(null=True, blank=True)

    is_public = models.BooleanField(default=False)

    # Sharing (resolved via permissions engine)
    shared_with = models.JSONField(default=list)  # [{type, id, permission}]

    class Meta:
        db_table = "reports"
        unique_together = [("workspace_id", "slug")]


class ReportSnapshot(UUIDPrimaryKeyMixin, TimestampMixin):
    """Point-in-time cached result of a report execution."""
    report_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    row_count = models.IntegerField(default=0)
    data = models.JSONField(default=list)  # up to 10k rows cached
    generated_by = models.UUIDField(null=True, blank=True)
    duration_ms = models.IntegerField(default=0)

    class Meta:
        db_table = "report_snapshots"
        indexes = [models.Index(fields=["report_id", "-created_at"])]


class Dashboard(TenantModel):
    """
    A collection of widgets arranged on a grid.
    """
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    layout = models.JSONField(default=list)  # react-grid-layout compatible
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    shared_with = models.JSONField(default=list)

    class Meta:
        db_table = "dashboards"
        unique_together = [("workspace_id", "slug")]


class DashboardWidget(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single widget on a dashboard.
    """
    WIDGET_TYPE = [
        ("report", "Report / Chart"),
        ("metric_card", "Metric Card (KPI)"),
        ("iframe", "Embedded iFrame"),
        ("text", "Text / Markdown"),
        ("activity_feed", "Activity Feed"),
        ("quick_links", "Quick Links"),
    ]

    dashboard_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    widget_type = models.CharField(max_length=25, choices=WIDGET_TYPE)
    title = models.CharField(max_length=255, blank=True)
    report_id = models.UUIDField(null=True, blank=True)  # for widget_type=report

    # Grid position (stored redundantly here + in Dashboard.layout)
    grid_x = models.IntegerField(default=0)
    grid_y = models.IntegerField(default=0)
    grid_w = models.IntegerField(default=6)
    grid_h = models.IntegerField(default=4)

    config = models.JSONField(default=dict)  # widget-specific config
    refresh_interval_seconds = models.IntegerField(default=0)  # 0=manual

    # Data lineage
    source_report_ids = models.JSONField(default=list)

    class Meta:
        db_table = "dashboard_widgets"
        indexes = [models.Index(fields=["dashboard_id"])]
