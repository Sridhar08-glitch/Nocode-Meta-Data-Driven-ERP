"""
Document / PDF templates (Phase 1.33).

A versioned, workspace-scoped PDF template bound to an entity: page config + header
field blocks + an optional line-item table over a related entity. Rendering reuses the
pluggable PDF engine from Phase 1.31 (reportlab today, weasyprint when GTK is present).
Triggerable from a record action / workflow step (render-by-record_id).
"""
from django.db import models

from apps.core.models import TenantModel


class DocumentTemplate(TenantModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100)
    entity_slug = models.SlugField(max_length=63)     # the bound entity
    page_config = models.JSONField(default=dict)      # {"title": "...", "subtitle": "..."}
    # blocks: header field list, e.g. [{"field": "name", "label": "Customer"}, ...]
    blocks = models.JSONField(default=list)
    # line_items: {"entity_slug": "invoice_line", "relation_field": "invoice",
    #              "columns": [{"key": "product", "label": "Product"}, ...]}
    line_items = models.JSONField(default=dict)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "document_templates"
        unique_together = [("workspace_id", "slug")]
        indexes = [models.Index(fields=["workspace_id", "entity_slug"])]

    def __str__(self):
        return f"{self.slug} v{self.version}"
