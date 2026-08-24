"""
Service helpers for authentication flows: client metadata extraction, token
creation/email dispatch, login-history recording, and MFA backup codes.

All token *values* are returned raw to the caller (for emailing) while only their
SHA-256 hashes are persisted.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .crypto import generate_token, hash_token
from .models import (
    ApiKey,
    EmailVerificationToken,
    LoginHistory,
    PasswordResetToken,
)

API_KEY_SCHEME = "nxk_"

EMAIL_VERIFY_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LEN = 10


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def get_user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:512]


# ── Email verification ──────────────────────────────────────────────────────
def create_email_verification_token(user):
    raw = generate_token()
    obj = EmailVerificationToken.objects.create(
        user=user,
        token_hash=hash_token(raw),
        expires_at=timezone.now() + EMAIL_VERIFY_TTL,
    )
    return raw, obj


def send_verification_email(user, raw_token: str):
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    send_mail(
        subject="Verify your Sridhar ERP email",
        message=f"Welcome to Sridhar ERP. Verify your email:\n\n{link}\n\nThis link expires in 24 hours.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def consume_email_verification_token(raw_token: str):
    """Return the matching unused, unexpired token or None."""
    try:
        obj = EmailVerificationToken.objects.select_related("user").get(
            token_hash=hash_token(raw_token), is_used=False
        )
    except EmailVerificationToken.DoesNotExist:
        return None
    if obj.expires_at <= timezone.now():
        return None
    return obj


# ── Email change ────────────────────────────────────────────────────────────
def create_email_change_token(user, new_email: str):
    """A verification token that, when consumed, switches the user's email to
    ``new_email`` (stored on the token; only its hash is otherwise persisted)."""
    raw = generate_token()
    obj = EmailVerificationToken.objects.create(
        user=user,
        token_hash=hash_token(raw),
        expires_at=timezone.now() + EMAIL_VERIFY_TTL,
        new_email=new_email.lower(),
    )
    return raw, obj


def send_email_change_verification(new_email: str, raw_token: str):
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    send_mail(
        subject="Confirm your new Sridhar ERP email",
        message=f"Confirm this address to finish changing your Sridhar ERP email:\n\n{link}\n\n"
                f"This link expires in 24 hours. If you did not request this, ignore this email.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[new_email],
        fail_silently=False,
    )


def send_password_changed_notice(user):
    """Security notice to the account's current address after a password change."""
    send_mail(
        subject="Your Sridhar ERP password was changed",
        message="Your Sridhar ERP password was just changed. If this was not you, reset your "
                "password immediately and review your active sessions.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


# ── Password reset ──────────────────────────────────────────────────────────
def create_password_reset_token(user):
    raw = generate_token()
    obj = PasswordResetToken.objects.create(
        user=user,
        token_hash=hash_token(raw),
        expires_at=timezone.now() + PASSWORD_RESET_TTL,
    )
    return raw, obj


def send_password_reset_email(user, raw_token: str):
    link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_mail(
        subject="Reset your Sridhar ERP password",
        message=f"Reset your password:\n\n{link}\n\nThis link expires in 1 hour. "
                f"If you did not request this, ignore this email.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def consume_password_reset_token(raw_token: str):
    try:
        obj = PasswordResetToken.objects.select_related("user").get(
            token_hash=hash_token(raw_token), is_used=False
        )
    except PasswordResetToken.DoesNotExist:
        return None
    if obj.expires_at <= timezone.now():
        return None
    return obj


# ── Login history ───────────────────────────────────────────────────────────
def record_login(request, *, email, success, user=None, failure_reason="", mfa_used=False):
    LoginHistory.objects.create(
        user=user,
        email_attempted=email,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        success=success,
        failure_reason=failure_reason[:100],
        mfa_used=mfa_used,
    )


# ── MFA backup codes ────────────────────────────────────────────────────────
def generate_backup_codes():
    """Return (raw_codes, hashed_codes). Raw shown once; hashes persisted."""
    raw = [generate_token(8)[:BACKUP_CODE_LEN] for _ in range(BACKUP_CODE_COUNT)]
    hashed = [hash_token(c) for c in raw]
    return raw, hashed


# ── API keys ────────────────────────────────────────────────────────────────
def create_api_key(user, name, *, workspace_id=None, scopes=None, expires_at=None):
    """
    Mint an API key of the form ``nxk_<prefix>.<secret>``.

    Returns ``(raw_key, ApiKey)``. Only the SHA-256 hash of the full key is
    persisted; the raw key is returned to the caller exactly once.
    """
    prefix = f"{API_KEY_SCHEME}{secrets.token_hex(4)}"  # e.g. nxk_1a2b3c4d (12 chars)
    secret = secrets.token_urlsafe(24)
    raw_key = f"{prefix}.{secret}"
    obj = ApiKey.objects.create(
        user=user,
        workspace_id=workspace_id,
        name=name,
        key_prefix=prefix,
        key_hash=hash_token(raw_key),
        scopes=scopes or [],
        expires_at=expires_at,
    )
    return raw_key, obj
