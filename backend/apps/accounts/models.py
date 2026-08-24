"""
Authentication & user models.
JWT RS256 auth, MFA (TOTP), Google OAuth, sessions, API keys.
"""
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_verified", True)
        return self.create_user(email, password, **extra)


class User(UUIDPrimaryKeyMixin, TimestampMixin, AbstractBaseUser, PermissionsMixin):
    """Global user — belongs to one or more workspaces via WorkspaceMember."""
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    locale = models.CharField(max_length=10, default="en")

    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    # MFA
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, blank=True)  # TOTP secret (Fernet-encrypted ⇒ longer than plaintext)
    mfa_backup_codes = models.JSONField(default=list)  # hashed backup codes
    passkey_credentials = models.JSONField(default=list)  # WebAuthn/passkey credential descriptors (§5.3)

    # Metadata
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"
        indexes = [models.Index(fields=["email"])]

    def __str__(self):
        return self.email

    @property
    def display_name(self):
        return self.full_name or self.email.split("@")[0]


class OAuthAccount(UUIDPrimaryKeyMixin, TimestampMixin):
    """Linked OAuth provider accounts (Google, etc.)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="oauth_accounts")
    provider = models.CharField(max_length=50)  # "google"
    provider_user_id = models.CharField(max_length=255)
    email = models.EmailField()
    access_token_ref = models.CharField(max_length=255, blank=True)  # reference only, not raw token
    refresh_token_ref = models.CharField(max_length=255, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)  # provider profile snapshot

    class Meta:
        db_table = "oauth_accounts"
        unique_together = [("provider", "provider_user_id")]

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id}"


class RefreshTokenFamily(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks JWT refresh token families for rotation + family invalidation.
    When any token in a family is reused after rotation, the whole family is killed.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="token_families")
    workspace_id = models.UUIDField(null=True, blank=True)
    family_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    current_jti = models.UUIDField(unique=True, db_index=True)  # JTI of the most-recent refresh token
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "refresh_token_families"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["current_jti"]),
        ]

    def revoke(self, reason="manual"):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.save(update_fields=["is_active", "revoked_at", "revoked_reason"])


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin):
    """Personal or workspace-scoped API keys."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    workspace_id = models.UUIDField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    key_prefix = models.CharField(max_length=16, db_index=True)  # first 8 chars visible
    key_hash = models.CharField(max_length=64)  # SHA-256 of full key
    scopes = models.JSONField(default=list)  # ["read", "write"] or specific permissions
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # Key rotation with a grace window (§5.3): the old key keeps working until
    # grace_period_ends_at so callers can migrate without downtime.
    rotated_at = models.DateTimeField(null=True, blank=True)
    grace_period_ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_keys"
        indexes = [models.Index(fields=["key_prefix", "is_active"])]


class EmailVerificationToken(UUIDPrimaryKeyMixin, TimestampMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    # When set, consuming this token changes the user's email to this address
    # (email-change verification). Blank ⇒ initial account-email verification.
    new_email = models.EmailField(blank=True, default="")

    class Meta:
        db_table = "email_verification_tokens"


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "password_reset_tokens"


class LoginHistory(UUIDPrimaryKeyMixin):
    """Append-only log of login attempts."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history", null=True, blank=True)
    email_attempted = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=100, blank=True)
    mfa_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "login_history"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["ip_address", "-created_at"]),
        ]
