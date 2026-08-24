"""
RBAC + ABAC permission models.
Role-based + attribute-based access control at module/entity/field/record level.
Backed by PostgreSQL Row-Level Security as mandatory second layer.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin

RESOURCE_TYPES = [
    ("workspace", "Workspace"),
    ("module", "Module"),
    ("entity", "Entity"),
    ("field", "Field"),
    ("record", "Record"),
    ("report", "Report"),
    ("workflow", "Workflow"),
    ("dashboard", "Dashboard"),
    ("document", "Document"),
]

ACTION_TYPES = [
    ("create", "Create"),
    ("read", "Read"),
    ("update", "Update"),
    ("delete", "Delete"),
    ("export", "Export"),
    ("import", "Import"),
    ("share", "Share"),
    ("admin", "Admin"),
    ("*", "All"),
]


class Role(UUIDPrimaryKeyMixin, TimestampMixin):
    """Custom role within a workspace."""
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=63)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)  # owner, admin, member, viewer
    is_active = models.BooleanField(default=True)
    parent_role = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)  # inheritance

    class Meta:
        db_table = "roles"
        unique_together = [("workspace_id", "slug")]
        indexes = [models.Index(fields=["workspace_id", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.workspace_id})"


class Permission(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single permission grant on a role.
    resource_id is NULL to mean "all resources of this type".
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    workspace_id = models.UUIDField(db_index=True)
    resource_type = models.CharField(max_length=30, choices=RESOURCE_TYPES)
    resource_id = models.UUIDField(null=True, blank=True)  # NULL = all
    action = models.CharField(max_length=30, choices=ACTION_TYPES)
    is_deny = models.BooleanField(default=False)  # explicit deny overrides allow

    # ABAC conditions (evaluated per-request against record attributes)
    conditions = models.JSONField(default=list)
    # Example: [{"field": "owner_id", "op": "eq", "value": "${actor.id}"}]

    class Meta:
        db_table = "permissions"
        indexes = [
            models.Index(fields=["role", "resource_type", "action"]),
            models.Index(fields=["workspace_id", "resource_type"]),
        ]


class DataMaskingRule(UUIDPrimaryKeyMixin, TimestampMixin):
    """Masks field values for roles below a threshold."""
    workspace_id = models.UUIDField(db_index=True)
    field_id = models.UUIDField()  # FieldDefinition.id
    role_id = models.UUIDField()   # Role.id — roles at or below this get masking
    mask_type = models.CharField(max_length=30)  # "full", "partial", "hash"
    mask_pattern = models.CharField(max_length=100, blank=True)  # e.g. "***@{domain}"

    class Meta:
        db_table = "data_masking_rules"


class FieldPermission(UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit read/write permission overrides at field level."""
    workspace_id = models.UUIDField(db_index=True)
    field_id = models.UUIDField(db_index=True)
    role_id = models.UUIDField(db_index=True)
    can_read = models.BooleanField(default=True)
    can_write = models.BooleanField(default=True)

    class Meta:
        db_table = "field_permissions"
        unique_together = [("field_id", "role_id")]
