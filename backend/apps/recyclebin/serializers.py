"""DRF serializers for the recycle bin API."""
from rest_framework import serializers

from .models import RecycleBinEntry


class RecycleBinEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecycleBinEntry
        fields = ["id", "entity_id", "entity_slug", "record_id", "record_title",
                  "deleted_by", "deleted_at", "purge_after", "cascade_entries",
                  "is_purged", "purged_at", "created_at"]
        read_only_fields = fields
