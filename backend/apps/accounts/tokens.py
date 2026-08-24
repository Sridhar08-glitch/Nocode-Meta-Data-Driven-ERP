"""
JWT token service — RS256 access/refresh tokens with rotating refresh-token
families and reuse detection.

Built on the existing ``accounts.RefreshTokenFamily`` ledger; this module holds only
the issuing/rotation logic (no new identity models).

Claims
------
access:  user_id, email, workspace_id?, token_type="access", jti, iat, exp
refresh: user_id, workspace_id?, token_type="refresh", family_id, jti, iat, exp
mfa:     user_id, token_type="mfa_challenge", jti, iat, exp  (5-minute challenge)
"""
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from django.conf import settings
from django.utils import timezone as dj_timezone
from rest_framework.exceptions import AuthenticationFailed

from .models import RefreshTokenFamily

MFA_CHALLENGE_LIFETIME = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(UTC)


def _sign(payload: dict) -> str:
    return jwt.encode(
        payload,
        settings.SIMPLE_JWT["SIGNING_KEY"],
        algorithm=settings.SIMPLE_JWT["ALGORITHM"],
    )


def _base_claims(token_type: str, lifetime: timedelta, *, exp_override=None) -> dict:
    iat = _now()
    exp = exp_override or (iat + lifetime)
    return {
        "token_type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }


def issue_access_token(user, workspace_id=None) -> str:
    """Return a signed 15-minute RS256 access token for *user*."""
    claims = _base_claims("access", settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"])
    claims.update({"user_id": str(user.id), "email": user.email})
    if workspace_id is not None:
        claims["workspace_id"] = str(workspace_id)
    return _sign(claims)


def issue_refresh_token(user, workspace_id=None, *, user_agent="", ip=None):
    """Create a new refresh-token family and return ``(raw_token, family)``."""
    expires_at = _now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    jti = uuid.uuid4()
    family = RefreshTokenFamily.objects.create(
        user=user,
        workspace_id=workspace_id,
        family_id=uuid.uuid4(),
        current_jti=jti,
        is_active=True,
        user_agent=(user_agent or "")[:512],
        ip_address=ip,
        expires_at=expires_at,
    )
    token = _build_refresh_token(user, family, jti, expires_at)
    return token, family


def _build_refresh_token(user, family, jti: uuid.UUID, expires_at: datetime) -> str:
    claims = _base_claims("refresh", None, exp_override=expires_at)
    claims["jti"] = str(jti)
    claims["user_id"] = str(user.id)
    claims["family_id"] = str(family.family_id)
    if family.workspace_id is not None:
        claims["workspace_id"] = str(family.workspace_id)
    return _sign(claims)


def decode_token(raw_token: str, *, expected_type=None) -> dict:
    """Decode + verify a token. Raises AuthenticationFailed on any problem."""
    try:
        payload = jwt.decode(
            raw_token,
            settings.SIMPLE_JWT["VERIFYING_KEY"],
            algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
            options={"require": ["exp", "iat", "jti", "token_type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationFailed("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationFailed(f"Invalid token: {exc}") from exc
    if expected_type and payload.get("token_type") != expected_type:
        raise AuthenticationFailed(f"Expected a {expected_type} token.")
    return payload


def rotate_refresh_token(raw_token: str, *, user_agent="", ip=None):
    """
    Rotate a refresh token.

    - Reuse detection: if the presented jti is not the family's current jti, the
      entire family is revoked and authentication fails.
    - On success: a new refresh jti is minted, ``current_jti`` advances, and a fresh
      ``(access_token, refresh_token)`` pair is returned.
    """
    payload = decode_token(raw_token, expected_type="refresh")
    family_id = payload.get("family_id")
    presented_jti = payload.get("jti")
    if not family_id or not presented_jti:
        raise AuthenticationFailed("Malformed refresh token.")

    try:
        family = RefreshTokenFamily.objects.select_related("user").get(family_id=family_id)
    except RefreshTokenFamily.DoesNotExist as exc:
        raise AuthenticationFailed("Unknown refresh token family.") from exc

    if not family.is_active:
        raise AuthenticationFailed("Refresh token family is no longer active.")
    if family.expires_at <= dj_timezone.now():
        family.revoke(reason="expired")
        raise AuthenticationFailed("Refresh token family has expired.")

    if str(family.current_jti) != str(presented_jti):
        # Reuse of an already-rotated token → compromise. Kill the whole family.
        family.revoke(reason="reuse_detected")
        raise AuthenticationFailed("Refresh token reuse detected; session revoked.")

    user = family.user
    if not user.is_active:
        family.revoke(reason="user_inactive")
        raise AuthenticationFailed("User is inactive.")

    new_jti = uuid.uuid4()
    family.current_jti = new_jti
    if user_agent:
        family.user_agent = user_agent[:512]
    if ip:
        family.ip_address = ip
    family.save(update_fields=["current_jti", "user_agent", "ip_address", "updated_at"])

    access = issue_access_token(user, family.workspace_id)
    refresh = _build_refresh_token(user, family, new_jti, family.expires_at)
    return access, refresh


def revoke_family(family_id, reason="logout") -> bool:
    """Revoke a refresh-token family. Returns True if a family was revoked."""
    try:
        family = RefreshTokenFamily.objects.get(family_id=family_id)
    except RefreshTokenFamily.DoesNotExist:
        return False
    if family.is_active:
        family.revoke(reason=reason)
    return True


def revoke_all_for_user(user, reason="password_reset") -> int:
    """Revoke every active family for *user*. Returns the count revoked."""
    qs = RefreshTokenFamily.objects.filter(user=user, is_active=True)
    count = qs.count()
    qs.update(is_active=False, revoked_at=dj_timezone.now(), revoked_reason=reason)
    return count


def issue_mfa_challenge_token(user) -> str:
    """Short-lived token proving password was verified, pending TOTP."""
    claims = _base_claims("mfa_challenge", MFA_CHALLENGE_LIFETIME)
    claims["user_id"] = str(user.id)
    return _sign(claims)


def issue_token_pair(user, workspace_id=None, *, user_agent="", ip=None):
    """Convenience: issue an ``(access, refresh)`` pair and the family."""
    access = issue_access_token(user, workspace_id)
    refresh, family = issue_refresh_token(user, workspace_id, user_agent=user_agent, ip=ip)
    return access, refresh, family
