"""
Session management (Phase 1.27).

A "session" is an active ``RefreshTokenFamily`` (one per login/device). These helpers
list and revoke families for the session-management UI; reuse detection and rotation
remain in :mod:`apps.accounts.tokens`.
"""
from __future__ import annotations

import uuid

from django.utils import timezone

from .models import RefreshTokenFamily


def list_sessions(user):
    """Active families for *user*, most-recently-seen first."""
    return RefreshTokenFamily.objects.filter(user=user, is_active=True).order_by("-updated_at")


def revoke_session(user, family_id) -> bool:
    """Revoke a single family owned by *user*. Returns True if one was revoked."""
    fam = RefreshTokenFamily.objects.filter(
        user=user, family_id=family_id, is_active=True).first()
    if fam is None:
        return False
    fam.revoke(reason="session_revoked")
    return True


def revoke_all_sessions(user, *, keep_family_id=None) -> int:
    """Revoke every active family for *user*, optionally keeping the current one."""
    qs = RefreshTokenFamily.objects.filter(user=user, is_active=True)
    if keep_family_id is not None:
        qs = qs.exclude(family_id=keep_family_id)
    count = qs.count()
    qs.update(is_active=False, revoked_at=timezone.now(), revoked_reason="revoke_all")
    return count


def _as_uuid(value):
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
