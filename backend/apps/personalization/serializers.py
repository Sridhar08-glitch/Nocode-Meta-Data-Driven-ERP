"""DRF serializer for the personalization API."""
from rest_framework import serializers

from .models import UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ["id", "values", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
