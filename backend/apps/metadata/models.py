"""
Metadata Engine — the heart of Sridhar ERP.
entity_definitions, field_definitions, schema_versions, modules.
Every ERP capability is a config here, not a separate codebase.
"""
from django.db import models

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class Module(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Top-level grouping: CRM, HRMS, Inventory, Projects, Helpdesk, Assets,
    Procurement, Accounting, Documents — plus custom workspace modules.
    """
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=63)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    is_system = models.BooleanField(default=False)  # built-in vs custom
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    settings = models.JSONField(default=dict)

    class Meta:
        db_table = "modules"
        unique_together = [("workspace_id", "slug")]


class EntityDefinition(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Defines a dynamic entity (e.g. "Lead", "Employee", "PurchaseOrder").
    Creates a real PostgreSQL table via physical_tables app.
    """
    ICON_CHOICES = []  # any string allowed

    workspace_id = models.UUIDField(db_index=True)
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name="entities")
    name = models.CharField(max_length=100)           # "Lead"
    plural_name = models.CharField(max_length=100)     # "Leads"
    slug = models.SlugField(max_length=63)             # "lead"
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Physical table config
    table_name = models.CharField(max_length=127, blank=True)  # e.g. "crm_leads"
    has_physical_table = models.BooleanField(default=False)

    # Features
    enable_activity = models.BooleanField(default=True)
    enable_comments = models.BooleanField(default=True)
    enable_attachments = models.BooleanField(default=True)
    enable_tagging = models.BooleanField(default=True)
    enable_recycle_bin = models.BooleanField(default=True)
    enable_versioning = models.BooleanField(default=False)

    # Record-level permissions (ABAC hooks)
    record_owner_field = models.CharField(max_length=63, blank=True)  # field slug pointing to owner

    # Config VCS
    current_schema_version = models.IntegerField(default=1)
    settings = models.JSONField(default=dict)

    # Primary display field
    title_field_slug = models.CharField(max_length=63, default="name")

    created_by = models.UUIDField(null=True, blank=True)
    updated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "entity_definitions"
        unique_together = [("workspace_id", "slug")]
        indexes = [models.Index(fields=["workspace_id", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.slug})"


FIELD_TYPE_CHOICES = [
    # Text
    ("text", "Text"),
    ("textarea", "Long Text"),
    ("rich_text", "Rich Text"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("url", "URL"),
    # Numbers
    ("integer", "Integer"),
    ("decimal", "Decimal"),
    ("currency", "Currency"),
    ("percent", "Percent"),
    # Date/Time
    ("date", "Date"),
    ("datetime", "Date & Time"),
    ("time", "Time"),
    ("duration", "Duration"),
    # Boolean
    ("boolean", "Checkbox"),
    # Select
    ("select", "Single Select"),
    ("multi_select", "Multi Select"),
    ("status", "Status"),
    # Relational
    ("lookup", "Lookup (FK)"),
    ("multi_lookup", "Multi Lookup (M2M)"),
    ("user", "User"),
    ("multi_user", "Multi User"),
    # Files
    ("file", "File"),
    ("image", "Image"),
    # Computed
    ("formula", "Formula"),
    ("rollup", "Rollup"),
    ("count", "Count"),
    # System
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
    ("created_by", "Created By"),
    ("updated_by", "Updated By"),
    ("auto_number", "Auto Number"),
    ("uuid", "UUID"),
    # Special
    ("json", "JSON"),
    ("rating", "Rating"),
    ("progress", "Progress"),
    ("location", "Location"),
    ("barcode", "Barcode / QR"),
]

FIELD_TYPE_VALUES = [c[0] for c in FIELD_TYPE_CHOICES]


class FieldDefinition(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Defines a single field on an EntityDefinition.
    filterable/sortable fields get promoted to real PostgreSQL columns.
    Others overflow into custom_data JSONB.
    """
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name="fields")
    workspace_id = models.UUIDField(db_index=True)  # denormalized for RLS

    name = models.CharField(max_length=100)      # "First Name"
    slug = models.SlugField(max_length=63)        # "first_name"
    field_type = models.CharField(max_length=30, choices=FIELD_TYPE_CHOICES)
    description = models.CharField(max_length=500, blank=True)

    # Column promotion to physical table
    is_promoted = models.BooleanField(default=False)  # has real PG column
    column_name = models.CharField(max_length=63, blank=True)  # actual PG column name

    # Indexing
    is_filterable = models.BooleanField(default=True)
    is_sortable = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=False)  # full-text search
    has_index = models.BooleanField(default=False)  # has PG index

    # Validation
    is_required = models.BooleanField(default=False)
    is_unique = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    validation_rules = models.JSONField(default=list)  # [{type, params, message}]

    # Display
    is_system = models.BooleanField(default=False)   # cannot be deleted
    is_hidden = models.BooleanField(default=False)
    is_readonly = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # SOFT DELETE ONLY — never hard-delete a field with data (§5.2)
    order = models.IntegerField(default=0)

    # Type-specific config
    config = models.JSONField(default=dict)
    # Examples:
    # select: {"options": [{"value": "open", "label": "Open", "color": "#..."}]}
    # lookup: {"target_entity_slug": "contact", "display_field": "name"}
    # formula: {"expression": "price * qty", "result_type": "decimal"}
    # rollup: {"source_entity": "invoice", "rollup_field": "amount", "function": "sum"}
    # currency: {"currency_code": "USD"}
    # decimal: {"precision": 2}

    # Permissions
    read_roles = models.JSONField(default=list)   # [] = all roles can read
    write_roles = models.JSONField(default=list)  # [] = all roles can write

    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "field_definitions"
        unique_together = [("entity", "slug")]
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["entity", "is_promoted"]),
            models.Index(fields=["workspace_id"]),
        ]

    def __str__(self):
        return f"{self.entity.slug}.{self.slug} ({self.field_type})"


class SchemaVersion(UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks DDL schema versions per entity for Config VCS / rollback."""
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name="schema_versions")
    workspace_id = models.UUIDField(db_index=True)
    version = models.IntegerField()
    snapshot = models.JSONField()  # full entity+field config at this version
    migration_sql = models.TextField(blank=True)  # the DDL applied
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.UUIDField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    parent_version = models.IntegerField(null=True, blank=True)
    commit_id = models.UUIDField(null=True, blank=True)  # config_vcs.Commit

    class Meta:
        db_table = "schema_versions"
        unique_together = [("entity", "version")]
        indexes = [models.Index(fields=["entity", "is_current"])]


class EntityPhysicalTable(UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks the physical PostgreSQL table status for each entity."""
    STATUS_CHOICES = [
        ("provisioning", "Provisioning"),
        ("ready", "Ready"),
        ("migrating", "Migrating"),
        ("error", "Error"),
    ]
    entity = models.OneToOneField(EntityDefinition, on_delete=models.CASCADE, related_name="physical_table")
    workspace_id = models.UUIDField(db_index=True)
    table_name = models.CharField(max_length=127)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="provisioning")
    promoted_columns = models.JSONField(default=list)  # [{slug, column_name, pg_type}]
    last_projection_event_id = models.UUIDField(null=True, blank=True)
    row_count = models.BigIntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "entity_physical_tables"


class ViewDefinition(UUIDPrimaryKeyMixin, TimestampMixin):
    """Saved views on entities (table, kanban, calendar, gantt, map, gallery)."""
    VIEW_TYPES = [
        ("table", "Table"),
        ("kanban", "Kanban"),
        ("calendar", "Calendar"),
        ("gantt", "Gantt"),
        ("gallery", "Gallery"),
        ("map", "Map"),
        ("timeline", "Timeline"),
        ("form", "Form"),
    ]
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name="views")
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    view_type = models.CharField(max_length=20, choices=VIEW_TYPES, default="table")
    config = models.JSONField(default=dict)  # columns, grouping, filters, sorts
    is_default = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = "view_definitions"


class FormDefinition(UUIDPrimaryKeyMixin, TimestampMixin):
    """Form layouts for entity record create/edit."""
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name="forms")
    workspace_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    layout = models.JSONField(default=list)  # [{section, fields, conditions}]
    settings = models.JSONField(default=dict)  # submit button text, redirect, etc.
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "form_definitions"
