"""DRF serializers for the marketplace API (PROJECT_HANDBOOK.md §34.4)."""
from rest_framework import serializers

from .models import InstalledPlugin, MarketplacePlugin, PluginVersion


class MarketplacePluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplacePlugin
        fields = ["id", "slug", "name", "tagline", "description", "category", "status",
                  "publisher_name", "is_official", "latest_version", "install_count",
                  "rating_sum", "rating_count", "icon_url", "screenshots",
                  "documentation_url", "source_url", "created_at", "updated_at"]
        read_only_fields = ["id", "install_count", "rating_sum", "rating_count",
                            "created_at", "updated_at"]


class PluginVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginVersion
        fields = ["id", "plugin_id", "version", "changelog", "manifest", "manifest_hash",
                  "is_published", "published_at", "created_at"]
        read_only_fields = ["id", "manifest_hash", "is_published", "published_at", "created_at"]


class PluginVersionListSerializer(serializers.ModelSerializer):
    """Lightweight — omits the (potentially large) manifest body."""
    class Meta:
        model = PluginVersion
        fields = ["id", "plugin_id", "version", "changelog", "is_published",
                  "published_at", "created_at"]
        read_only_fields = fields


class InstalledPluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstalledPlugin
        fields = ["id", "plugin_id", "plugin_version_id", "plugin_slug", "installed_version",
                  "status", "installed_by", "installed_at", "created_entity_ids",
                  "created_workflow_ids", "created_rule_ids", "created_report_ids",
                  "error_message", "created_at", "updated_at"]
        read_only_fields = fields
