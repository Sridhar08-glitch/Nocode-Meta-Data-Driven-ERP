"""
Business Process Catalog (Phase 1.34).

A curated, GLOBAL catalog of packaged business processes (entities + workflows + rules +
reports + notification templates) expressed as a marketplace-compatible manifest. Browse
+ preview + install-into-a-workspace; install reuses the marketplace manifest applier.
Global (no workspace_id) like marketplace plugins — it is the same catalog concept.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class ProcessBlueprint(UUIDPrimaryKeyMixin, TimestampMixin):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    manifest = models.JSONField(default=dict)   # marketplace-compatible manifest
    is_published = models.BooleanField(default=False)
    install_count = models.IntegerField(default=0)

    class Meta:
        db_table = "process_blueprints"
        indexes = [models.Index(fields=["is_published", "category"])]

    def __str__(self):
        return f"{self.slug} ({'published' if self.is_published else 'draft'})"
