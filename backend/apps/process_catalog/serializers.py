"""DRF serializers for the process catalog."""
from rest_framework import serializers

from .models import ProcessBlueprint


class ProcessBlueprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessBlueprint
        fields = ["id", "name", "slug", "category", "description", "publisher",
                  "manifest", "is_published", "install_count", "created_at", "updated_at"]
        read_only_fields = ["id", "install_count", "created_at", "updated_at"]
