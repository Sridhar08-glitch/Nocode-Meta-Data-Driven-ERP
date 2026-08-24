"""
Portal JWT token service — a SEPARATE auth realm from workspace users.

Tokens carry ``token_type`` of ``portal_access`` / ``portal_refresh`` and a
``portal_user_id`` claim (never ``user_id``), so a portal token can never satisfy
a workspace endpoint and vice-versa. Refresh families are tracked in
``portal.PortalSession`` (mirrors accounts.RefreshTokenFamily).
"""
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from django.conf import settings
from django.utils import timezone as dj_timezone
from rest_framework.exceptions import AuthenticationFailed

from .models import PortalSession

ACCESS_LIFETIME = timedelta(minutes=15)
REFRESH_LIFETIME = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(UTC)


def _sign(payload: dict) -> str:
    return jwt.encode(payload, settings.SIMPLE_JWT["SIGNING_KEY"],
                      algorithm=settings.SIMPLE_JWT["ALGORITHM"])


def _claims(token_type: str, lifetime: timedelta, *, exp_override=None) -> dict:
    iat = _now()
    exp = exp_override or (iat + lifetime)
    return {
        "token_type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }


def issue_portal_access(portal_user) -> str:
    c = _claims("portal_access", ACCESS_LIFETIME)
    c["portal_user_id"] = str(portal_user.id)
    c["workspace_id"] = str(portal_user.workspace_id)
    return _sign(c)


def issue_portal_refresh(portal_user, *, user_agent="", ip=None):
    expires_at = _now() + REFRESH_LIFETIME
    jti = uuid.uuid4()
    session = PortalSession.objects.create(
        portal_user_id=portal_user.id,
        workspace_id=portal_user.workspace_id,
        family_id=uuid.uuid4(),
        current_jti=str(jti),
        is_active=True,
        user_agent=(user_agent or "")[:500],
        ip_address=ip,
    )
    return _build_refresh(portal_user, session, jti, expires_at), session


def _build_refresh(portal_user, session, jti, expires_at) -> str:
    c = _claims("portal_refresh", None, exp_override=expires_at)
    c["jti"] = str(jti)
    c["portal_user_id"] = str(portal_user.id)
    c["workspace_id"] = str(portal_user.workspace_id)
    c["family_id"] = str(session.family_id)
    return _sign(c)


def decode_portal_token(raw_token: str, *, expected_type=None) -> dict:
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


def issue_portal_pair(portal_user, *, user_agent="", ip=None):
    access = issue_portal_access(portal_user)
    refresh, session = issue_portal_refresh(portal_user, user_agent=user_agent, ip=ip)
    return access, refresh, session


def rotate_portal_refresh(raw_token: str, *, user_agent="", ip=None):
    from .models import PortalUser

    payload = decode_portal_token(raw_token, expected_type="portal_refresh")
    family_id = payload.get("family_id")
    presented_jti = payload.get("jti")
    if not family_id or not presented_jti:
        raise AuthenticationFailed("Malformed refresh token.")
    try:
        session = PortalSession.objects.get(family_id=family_id)
    except PortalSession.DoesNotExist as exc:
        raise AuthenticationFailed("Unknown portal session.") from exc
    if not session.is_active:
        raise AuthenticationFailed("Portal session is no longer active.")
    if str(session.current_jti) != str(presented_jti):
        session.is_active = False
        session.revoked_at = dj_timezone.now()
        session.revoked_reason = "reuse_detected"
        session.save(update_fields=["is_active", "revoked_at", "revoked_reason"])
        raise AuthenticationFailed("Portal token reuse detected; session revoked.")

    portal_user = PortalUser.objects.get(pk=session.portal_user_id)
    if not portal_user.is_active:
        raise AuthenticationFailed("Portal user is inactive.")

    new_jti = uuid.uuid4()
    session.current_jti = str(new_jti)
    session.last_used_at = dj_timezone.now()
    session.save(update_fields=["current_jti", "last_used_at"])
    access = issue_portal_access(portal_user)
    refresh = _build_refresh(portal_user, session, new_jti, _now() + REFRESH_LIFETIME)
    return access, refresh


def revoke_portal_session(family_id, reason="logout") -> bool:
    try:
        session = PortalSession.objects.get(family_id=family_id)
    except PortalSession.DoesNotExist:
        return False
    if session.is_active:
        session.is_active = False
        session.revoked_at = dj_timezone.now()
        session.revoked_reason = reason
        session.save(update_fields=["is_active", "revoked_at", "revoked_reason"])
    return True
