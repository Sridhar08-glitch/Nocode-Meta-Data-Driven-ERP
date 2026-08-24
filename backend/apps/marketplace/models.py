"""
Feature Marketplace — self-contained plugin packages.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class MarketplacePlugin(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Plugin definition (published to the marketplace).
    Plugins can ship: modules, entity defs, workflows, rules, reports, dashboards.
    """
    STATUS = [
        ("draft", "Draft"),
        ("review", "Under Review"),
        ("published", "Published"),
        ("deprecated", "Deprecated"),
        ("removed", "Removed"),
    ]
    CATEGORY = [
        ("crm", "CRM"),
        ("hr", "HR"),
        ("finance", "Finance"),
        ("project", "Project Management"),
        ("inventory", "Inventory"),
        ("support", "Support"),
        ("marketing", "Marketing"),
        ("integration", "Integration"),
        ("utility", "Utility"),
    ]

    slug = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    tagline = models.CharField(max_length=500)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY)
    status = models.CharField(max_length=20, choices=STATUS, default="draft")

    # Publisher
    publisher_id = models.UUIDField(null=True, blank=True)  # workspace that published
    publisher_name = models.CharField(max_length=255, blank=True)
    is_official = models.BooleanField(default=False)

    # Versioning
    latest_version = models.CharField(max_length=30, blank=True)

    # Metrics
    install_count = models.IntegerField(default=0)
    rating_sum = models.IntegerField(default=0)
    rating_count = models.IntegerField(default=0)

    icon_url = models.CharField(max_length=2000, blank=True)
    screenshots = models.JSONField(default=list)
    documentation_url = models.CharField(max_length=2000, blank=True)
    source_url = models.CharField(max_length=2000, blank=True)

    class Meta:
        db_table = "marketplace_plugins"


class PluginVersion(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A specific versioned release of a plugin.
    Contains the full package manifest as JSON.
    """
    plugin_id = models.UUIDField(db_index=True)
    version = models.CharField(max_length=30)  # semver e.g. "1.2.3"
    changelog = models.TextField(blank=True)

    # Full plugin package contents
    manifest = models.JSONField()
    # manifest structure:
    # { "requires_nexus_version": ">=1.0.0",
    #   "modules": [...EntityDefinition dicts...],
    #   "workflows": [...WorkflowDefinition dicts...],
    #   "rules": [...BusinessRule dicts...],
    #   "reports": [...Report dicts...],
    #   "dashboards": [...Dashboard dicts...],
    #   "permissions": [...role dicts...] }

    # SHA-256 of manifest JSON for integrity
    manifest_hash = models.CharField(max_length=64)

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "plugin_versions"
        unique_together = [("plugin_id", "version")]


class InstalledPlugin(TenantModel):
    """
    Tracks a plugin installed in a workspace.
    """
    STATUS = [
        ("installing", "Installing"),
        ("active", "Active"),
        ("error", "Error"),
        ("disabled", "Disabled"),
        ("uninstalling", "Uninstalling"),
    ]

    plugin_id = models.UUIDField(db_index=True)
    plugin_version_id = models.UUIDField(db_index=True)
    plugin_slug = models.CharField(max_length=100)
    installed_version = models.CharField(max_length=30)

    status = models.CharField(max_length=20, choices=STATUS, default="installing")
    installed_by = models.UUIDField(null=True, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)

    # Config overrides supplied at install time
    config = models.JSONField(default=dict)

    # IDs of objects created during install (for clean uninstall)
    created_module_ids = models.JSONField(default=list)
    created_entity_ids = models.JSONField(default=list)
    created_workflow_ids = models.JSONField(default=list)
    created_rule_ids = models.JSONField(default=list)
    created_report_ids = models.JSONField(default=list)

    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "installed_plugins"
        unique_together = [("workspace_id", "plugin_slug")]
