"""
Data Lineage — end-to-end tracking of Record→Workflow→Report→Dashboard.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class LineageNode(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A node in the lineage graph. Represents any addressable object
    that produces or consumes data.
    """
    NODE_TYPE = [
        ("entity", "Entity Definition"),
        ("field", "Field Definition"),
        ("record", "Record"),
        ("report", "Report"),
        ("dashboard", "Dashboard"),
        ("widget", "Dashboard Widget"),
        ("workflow", "Workflow"),
        ("workflow_step", "Workflow Step"),
        ("import_job", "Import Job"),
        ("export_job", "Export Job"),
        ("api_endpoint", "API Endpoint"),
        ("form", "Public Form"),
    ]

    workspace_id = models.UUIDField(db_index=True)
    node_type = models.CharField(max_length=25, choices=NODE_TYPE)
    object_id = models.UUIDField(db_index=True)    # FK to the actual object
    object_slug = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "lineage_nodes"
        unique_together = [("workspace_id", "node_type", "object_id")]
        indexes = [models.Index(fields=["workspace_id", "node_type"])]


class LineageEdge(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A directed edge: source_node → target_node with relationship label.
    E.g. "entity:Contact" --reads--> "report:monthly_revenue"
    """
    EDGE_TYPE = [
        ("reads", "Reads"),
        ("writes", "Writes"),
        ("triggers", "Triggers"),
        ("produces", "Produces"),
        ("consumes", "Consumes"),
        ("derives_from", "Derives From"),
        ("references", "References"),
    ]

    workspace_id = models.UUIDField(db_index=True)
    source_node_id = models.UUIDField(db_index=True)
    target_node_id = models.UUIDField(db_index=True)
    edge_type = models.CharField(max_length=20, choices=EDGE_TYPE)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "lineage_edges"
        unique_together = [("workspace_id", "source_node_id", "target_node_id", "edge_type")]
        indexes = [
            models.Index(fields=["workspace_id", "source_node_id"]),
            models.Index(fields=["workspace_id", "target_node_id"]),
        ]
