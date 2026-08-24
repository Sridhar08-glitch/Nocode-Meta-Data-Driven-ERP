"""DRF serializers for the localization API."""
from rest_framework import serializers

from .models import EntityLabelTranslation, TranslationKey, WorkspaceLocale


class WorkspaceLocaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceLocale
        fields = ["id", "default_locale", "default_timezone", "default_currency",
                  "enabled_locales", "date_format", "time_format",
                  "number_decimal_separator", "number_thousands_separator",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TranslationKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslationKey
        fields = ["id", "namespace", "key", "default_value", "description", "is_system"]
        read_only_fields = fields


class EntityLabelTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityLabelTranslation
        fields = ["id", "locale", "entity_id", "field_id", "singular", "plural",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
