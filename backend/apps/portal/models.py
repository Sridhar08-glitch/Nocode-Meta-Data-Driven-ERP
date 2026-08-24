"""
Customer / Partner Portal — separate auth realm from workspace_members.
Portal users authenticate independently and see only permitted records.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class PortalConfiguration(TenantModel):
    """
    Workspace-level portal settings: branding, allowed entities, domains.
    One configuration per workspace (enforced at service layer).
    """
    is_enabled = models.BooleanField(default=False)
    name = models.CharField(max_length=255)
    custom_domain = models.CharField(max_length=253, blank=True)
    logo_url = models.CharField(max_length=2000, blank=True)
    primary_color = models.CharField(max_length=7, blank=True)

    # Which entity definitions are exposed on the portal
    exposed_entity_ids = models.JSONField(default=list)

    # Default role assigned to new portal signups
    default_role_id = models.UUIDField(null=True, blank=True)

    # Allow self-registration
    allow_self_signup = models.BooleanField(default=False)
    signup_domain_whitelist = models.JSONField(default=list)  # ["@acme.com"]

    welcome_message = models.TextField(blank=True)

    class Meta:
        db_table = "portal_configurations"
        unique_together = [("workspace_id",)]


class PortalUser(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A portal user — completely separate from User / WorkspaceMember.
    Cannot access workspace_members endpoints.
    """
    workspace_id = models.UUIDField(db_index=True)
    email = models.EmailField(db_index=True)
    full_name = models.CharField(max_length=255)
    avatar_url = models.CharField(max_length=2000, blank=True)

    # Hashed password (separate from workspace user passwords)
    password_hash = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # MFA
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, blank=True)  # stored encrypted

    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Linked record (e.g. the Contact record this portal user maps to)
    linked_entity_id = models.UUIDField(null=True, blank=True)
    linked_record_id = models.UUIDField(null=True, blank=True, db_index=True)

    role_id = models.UUIDField(null=True, blank=True)

    # Portal type drives capability sets (customer / vendor / partner / employee_ss …).
    portal_type = models.CharField(max_length=30, default="customer")

    class Meta:
        db_table = "portal_users"
        unique_together = [("workspace_id", "email")]

    # Minimal auth-user interface so DRF's IsAuthenticated works for the portal realm.
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class PortalUserToken(UUIDPrimaryKeyMixin):
    """Email verification / password reset tokens for portal users."""
    TOKEN_TYPE = [
        ("email_verify", "Email Verification"),
        ("password_reset", "Password Reset"),
        ("invite", "Invite"),
    ]

    portal_user_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField()
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPE)
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "portal_user_tokens"
        indexes = [models.Index(fields=["portal_user_id", "token_type"])]


class PortalSession(UUIDPrimaryKeyMixin):
    """Portal user refresh-token family tracking (mirrors RefreshTokenFamily)."""
    portal_user_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    family_id = models.UUIDField(unique=True)
    current_jti = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=50, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "portal_sessions"
        indexes = [models.Index(fields=["portal_user_id", "is_active"])]


class PortalEntityGrant(TenantModel):
    """
    Per-entity capability for portal users (Phase 1.34).

    Defines which entity a portal type may access and the ``link_field`` on that entity
    that must equal the portal user's ``linked_record_id`` — this is the server-enforced
    row scope (a portal user can only ever see records linked to them).
    """
    entity_slug = models.SlugField(max_length=63)
    # "" = applies to every portal type; otherwise must match PortalUser.portal_type
    portal_type = models.CharField(max_length=30, blank=True, default="")
    link_field = models.SlugField(max_length=63)   # field on the entity to match
    # Indirect (relationship) scoping (Phase P3.1A): when set, ``link_field`` is matched against
    # the VALUE of ``link_source`` on the portal user's OWN linked record (one hop through a
    # parent) instead of the raw ``linked_record_id``. Blank = direct match (the default). Enables
    # group-membership portals reusably: student→class, patient→ward, member→chapter, tenant→unit.
    link_source = models.SlugField(max_length=63, blank=True, default="")
    can_read = models.BooleanField(default=True)
    can_create = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)

    class Meta:
        db_table = "portal_entity_grants"
        unique_together = [("workspace_id", "entity_slug", "portal_type")]
        indexes = [models.Index(fields=["workspace_id", "entity_slug"])]
