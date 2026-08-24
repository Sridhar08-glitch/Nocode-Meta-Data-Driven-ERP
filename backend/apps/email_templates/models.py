"""
Email templates (Phase 1.33).

Server-side authored, versioned email templates with ``${var}`` placeholders (safe
``string.Template`` — never eval), HTML sanitised on render, with locale variants. One
row per (workspace, slug, locale). Rendering + test-send reuse the notifications renderer
and Django mail; the from-address comes from workspace branding.
"""
from django.db import models

from apps.core.models import TenantModel


class EmailTemplate(TenantModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100)
    locale = models.CharField(max_length=10, default="en")
    subject_template = models.CharField(max_length=500, blank=True)
    body_html = models.TextField(blank=True)          # ${var} placeholders, HTML
    blocks = models.JSONField(default=list)           # optional structured block definition
    variables = models.JSONField(default=list)        # declared variable names (for the editor)
    version = models.IntegerField(default=1)          # bumped when content changes
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "email_templates"
        unique_together = [("workspace_id", "slug", "locale")]
        indexes = [models.Index(fields=["workspace_id", "slug"])]

    def __str__(self):
        return f"{self.slug}@{self.locale} v{self.version}"
