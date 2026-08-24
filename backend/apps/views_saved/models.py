"""
Saved Views — personal and shared view configurations per member.
ViewDefinition (in metadata) is the canonical view template.
SavedView here is a member's customized instance with filters/sorts/column widths.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class SavedView(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A member's personalized copy/customization of a ViewDefinition.
    Stores column widths, hidden fields, personal filters, sort overrides.
    """
    workspace_id = models.UUIDField(db_index=True)
    view_definition_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField(db_index=True)
    member_id = models.UUIDField(db_index=True)

    name = models.CharField(max_length=255, blank=True)  # personal rename

    # Overrides (merged with base ViewDefinition at render time)
    hidden_field_slugs = models.JSONField(default=list)
    column_widths = models.JSONField(default=dict)     # {"field_slug": 120}
    personal_filters = models.JSONField(default=list)  # additional filter conditions
    sort_overrides = models.JSONField(default=list)    # [{field, direction}]
    group_by_override = models.CharField(max_length=100, blank=True)

    # Pinned / starred
    is_pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "saved_views"
        unique_together = [("workspace_id", "view_definition_id", "member_id")]
        indexes = [models.Index(fields=["workspace_id", "member_id"])]
