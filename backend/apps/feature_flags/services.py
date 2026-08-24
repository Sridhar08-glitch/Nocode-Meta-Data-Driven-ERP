"""
Feature-flag resolution (Phase 1.29).

Resolution precedence (highest first):
    user override  >  role override  >  workspace-wide override  >  rollout/default

Rollout is deterministic: a flag at ``rollout_percent`` is on for a subject iff
``hash(workspace_id : key : subject) % 100 < rollout_percent`` — stable across calls,
so a given user keeps the same on/off result for a flag.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from .models import FeatureFlag, FeatureFlagOverride


class FeatureFlagError(Exception):  # noqa: N818 — domain error
    pass


def rollout_bucket(workspace_id, key: str, subject_id) -> int:
    """Stable 0–99 bucket for (workspace, flag, subject)."""
    h = hashlib.sha256(f"{workspace_id}:{key}:{subject_id}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def _resolve_one(flag: FeatureFlag, overrides: list, user_id, role_ids: set) -> bool:
    # 1. user override
    for o in overrides:
        if o.target_type == "user" and user_id and str(o.target_id) == str(user_id):
            return o.enabled
    # 2. role override (any matching role in the caller's chain; enabled wins)
    role_ovs = [o for o in overrides
                if o.target_type == "role" and str(o.target_id) in role_ids]
    if role_ovs:
        return any(o.enabled for o in role_ovs)
    # 3. workspace-wide override
    for o in overrides:
        if o.target_type == "workspace":
            return o.enabled
    # 4. default + deterministic rollout
    if not flag.enabled:
        return False
    if flag.rollout_percent >= 100:
        return True
    if flag.rollout_percent <= 0:
        return False
    subject = user_id or flag.workspace_id
    return rollout_bucket(flag.workspace_id, flag.key, subject) < flag.rollout_percent


def resolve_flags(workspace_id, *, user_id=None, role_ids=None) -> dict:
    """Return ``{key: {"enabled": bool, "config": {...}}}`` for the caller."""
    role_ids = {str(r) for r in (role_ids or [])}
    overrides_by_flag = defaultdict(list)
    for o in FeatureFlagOverride.objects.filter(workspace_id=workspace_id):
        overrides_by_flag[o.flag_id].append(o)

    out = {}
    for flag in FeatureFlag.objects.filter(workspace_id=workspace_id, is_active=True):
        out[flag.key] = {
            "enabled": _resolve_one(flag, overrides_by_flag.get(flag.id, []), user_id, role_ids),
            "config": flag.config or {},
        }
    return out


def is_enabled(workspace_id, key: str, *, user_id=None, role_ids=None) -> bool:
    """Convenience single-flag check (False if the flag does not exist)."""
    flag = FeatureFlag.objects.filter(
        workspace_id=workspace_id, key=key, is_active=True).first()
    if flag is None:
        return False
    overrides = list(flag.overrides.all())
    return _resolve_one(flag, overrides, user_id, {str(r) for r in (role_ids or [])})
