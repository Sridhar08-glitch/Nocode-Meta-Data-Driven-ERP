"""DRF serializers for the search API."""
from rest_framework import serializers

from .models import RecentSearch, SavedSearch, SearchIndex


class SearchIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchIndex
        fields = ["id", "entity_id", "entity_slug", "indexed_field_slugs",
                  "field_weights", "config_updated_at", "last_reindex_at",
                  "indexed_row_count", "created_at", "updated_at"]
        read_only_fields = ["id", "config_updated_at", "last_reindex_at",
                            "indexed_row_count", "created_at", "updated_at"]


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = ["id", "name", "entity_id", "nql_ast", "nql_source", "created_by",
                  "is_shared", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class RecentSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentSearch
        fields = ["id", "query_text", "entity_slug", "result_count", "searched_at"]
        read_only_fields = fields
