"""
Tenancy models: workspaces, organisations, members, departments, teams, branches.
All workspace-scoped data is isolated by workspace_id + PostgreSQL RLS.
"""
from django.db import models

from apps.core.models import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Top-level tenant boundary. Every piece of ERP data belongs to exactly one workspace."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=63, unique=True, db_index=True)
    logo_url = models.URLField(blank=True)
    plan = models.CharField(max_length=50, default="free")  # free, starter, pro, enterprise
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT,
        related_name="owned_workspaces", null=True
    )
    # Limits (overridable per plan)
    max_members = models.IntegerField(default=5)
    max_entities = models.IntegerField(default=20)
    max_records = models.BigIntegerField(default=10_000)
    max_storage_bytes = models.BigIntegerField(default=1_073_741_824)  # 1 GB
    # Settings (JSONB-style)
    settings = models.JSONField(default=dict)

    class Meta:
        db_table = "workspaces"
        indexes = [models.Index(fields=["slug"])]

    def __str__(self):
        return f"{self.name} ({self.slug})"


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Links a User to a Workspace with a role."""
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
        ("viewer", "Viewer"),
        ("portal", "Portal"),  # external portal user
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("invited", "Invited"),
        ("suspended", "Suspended"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="invited")
    invite_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    invited_by = models.UUIDField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    # Fine-grained role assignment (references permissions.Role)
    custom_role_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "workspace_members"
        unique_together = [("workspace", "user")]
        indexes = [models.Index(fields=["workspace", "role", "status"])]

    def __str__(self):
        return f"{self.user_id} @ {self.workspace_id} [{self.role}]"


class WorkspaceInvitation(UUIDPrimaryKeyMixin, TimestampMixin):
    """A pending invitation to join a workspace.

    Auth-adjacent identity record (consumed by users who may not yet be members),
    so — like ``WorkspaceMember`` — it is RLS-exempt; workspace isolation is enforced
    in the service/views. Only the SHA-256 hash of the invite token is stored.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.UUIDField(null=True, blank=True)
    expires_at = models.DateTimeField()
    accepted_by = models.UUIDField(null=True, blank=True)  # User.id who accepted
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workspace_invitations"
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["email", "status"]),
        ]

    def __str__(self):
        return f"invite {self.email} → {self.workspace_id} [{self.status}]"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin):
    """Optional org layer within a workspace (holding company / group)."""
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="organizations")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "organizations"
        indexes = [models.Index(fields=["workspace"])]


class Department(UUIDPrimaryKeyMixin, TimestampMixin):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="departments")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="departments")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    head = models.UUIDField(null=True, blank=True)  # WorkspaceMember.id
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")

    class Meta:
        db_table = "departments"


class Team(UUIDPrimaryKeyMixin, TimestampMixin):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(WorkspaceMember, blank=True, related_name="teams")

    class Meta:
        db_table = "teams"


class Branch(UUIDPrimaryKeyMixin, TimestampMixin):
    """Physical or virtual branch/location within a workspace."""
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    address = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "branches"


class IPAllowlist(UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-workspace IP allowlist for admin access restriction."""
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="ip_allowlist")
    cidr = models.CharField(max_length=50)  # e.g. "192.168.1.0/24"
    label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ip_allowlist"
