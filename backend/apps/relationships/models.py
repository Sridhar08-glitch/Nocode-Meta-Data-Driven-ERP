"""
Relationships — typed links between records across entities.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class RelationshipDefinition(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Defines a named relationship type between two entity definitions.
    E.g. "Account has many Contacts", "Deal belongs to Account".
    """
    CARDINALITY = [
        ("one_to_one", "One-to-One"),
        ("one_to_many", "One-to-Many"),
        ("many_to_many", "Many-to-Many"),
        ("self_ref", "Self-Referencing"),
    ]

    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)

    # Source side
    source_entity_id = models.UUIDField(db_index=True)
    source_field_slug = models.CharField(max_length=100, blank=True)  # lookup field slug

    # Target side
    target_entity_id = models.UUIDField(db_index=True)
    target_field_slug = models.CharField(max_length=100, blank=True)  # reverse lookup field slug

    cardinality = models.CharField(max_length=20, choices=CARDINALITY)

    # Many-to-many junction table name (auto-generated)
    junction_table = models.CharField(max_length=63, blank=True)

    # Cascade behaviour
    on_delete = models.CharField(
        max_length=20,
        choices=[
            ("protect", "Protect"),
            ("cascade", "Cascade"),
            ("set_null", "Set Null"),
            ("detach", "Detach"),
        ],
        default="detach",
    )

    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "relationship_definitions"
        unique_together = [("workspace_id", "source_entity_id", "slug")]
        indexes = [
            models.Index(fields=["workspace_id", "source_entity_id"]),
            models.Index(fields=["workspace_id", "target_entity_id"]),
        ]


class RecordRelationship(UUIDPrimaryKeyMixin):
    """
    Instance link between two records (used for many-to-many or flexible
    cross-entity linking when junction tables aren't generated).
    """
    workspace_id = models.UUIDField(db_index=True)
    definition_id = models.UUIDField(db_index=True)

    source_entity_id = models.UUIDField()
    source_record_id = models.UUIDField(db_index=True)

    target_entity_id = models.UUIDField()
    target_record_id = models.UUIDField(db_index=True)

    sort_order = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict)  # extra edge data

    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "record_relationships"
        unique_together = [
            ("workspace_id", "definition_id", "source_record_id", "target_record_id")
        ]
        indexes = [
            models.Index(fields=["workspace_id", "source_record_id"]),
            models.Index(fields=["workspace_id", "target_record_id"]),
        ]
