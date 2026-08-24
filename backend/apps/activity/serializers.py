"""DRF serializers for the activity feed + comments API."""
from rest_framework import serializers

from .models import ActivityEntry, Comment


class ActivityEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityEntry
        fields = ["id", "workspace_id", "entity_id", "record_id", "activity_type",
                  "actor_id", "actor_type", "actor_name", "summary", "changes",
                  "event_sequence", "occurred_at", "is_pinned"]
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "entity_id", "record_id", "author_id", "author_type",
                  "parent_id", "body", "body_format", "mentions", "is_edited",
                  "is_deleted", "is_pinned", "created_at", "updated_at"]
        read_only_fields = ["id", "entity_id", "record_id", "author_id",
                            "author_type", "mentions", "is_edited", "is_deleted",
                            "is_pinned", "created_at", "updated_at"]
