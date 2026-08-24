"""
Localization — per-workspace language packs and translation overrides.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceLocale(TenantModel):
    """
    Locale settings for a workspace (default + allowed locales).
    One row per workspace_id (enforced at service layer).
    """
    default_locale = models.CharField(max_length=10, default="en-US")
    default_timezone = models.CharField(max_length=63, default="UTC")
    default_currency = models.CharField(max_length=3, default="USD")  # ISO 4217

    # Which locales workspace members can switch to
    enabled_locales = models.JSONField(default=list)  # ["en-US", "fr-FR", "de-DE"]

    # Number/date formatting overrides (null = locale defaults)
    date_format = models.CharField(max_length=30, blank=True)
    time_format = models.CharField(max_length=20, blank=True)
    number_decimal_separator = models.CharField(max_length=1, default=".")
    number_thousands_separator = models.CharField(max_length=1, default=",")

    class Meta:
        db_table = "workspace_locales"
        unique_together = [("workspace_id",)]


class TranslationKey(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A translatable string key (system-defined or workspace-custom).
    System keys ship with Nexus and cannot be deleted.
    """
    namespace = models.CharField(max_length=100)  # e.g. "ui", "emails", "modules.crm"
    key = models.CharField(max_length=255)         # e.g. "button.save"
    default_value = models.TextField()            # English default
    description = models.CharField(max_length=500, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "translation_keys"
        unique_together = [("namespace", "key")]


class TranslationOverride(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Workspace-level or entity-label-level translation override.
    Overrides the system default for a given locale.
    """
    workspace_id = models.UUIDField(db_index=True)
    key_id = models.UUIDField(db_index=True)
    locale = models.CharField(max_length=10)
    value = models.TextField()
    updated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "translation_overrides"
        unique_together = [("workspace_id", "key_id", "locale")]
        indexes = [models.Index(fields=["workspace_id", "locale"])]


class EntityLabelTranslation(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Translated labels for entity/field names shown in the UI.
    Separate from generic translation keys.
    """
    workspace_id = models.UUIDField(db_index=True)
    locale = models.CharField(max_length=10)

    # Either entity_id or field_id is set (not both)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)
    field_id = models.UUIDField(null=True, blank=True, db_index=True)

    singular = models.CharField(max_length=255, blank=True)
    plural = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "entity_label_translations"
        unique_together = [("workspace_id", "locale", "entity_id", "field_id")]
