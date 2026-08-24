"""
Personalization resolver (Phase P0).

``resolve_appearance()`` is a sibling of ``feature_flags.services.resolve_flags``:
it merges the appearance-preference layers with a fixed precedence and honours the
workspace admin lock policy (``WorkspaceBranding.locked_fields``):

    locked key    → workspace value wins (the user override is ignored)
    unlocked key  → user override  >  workspace default  >  system default

Accessibility keys (font_scale / high_contrast / reduced_motion) are never lockable
(``registry`` enforces this), so a user can always adjust them. ``role_ids`` is accepted
for signature parity with ``resolve_flags`` and future role-default layering (not part of P0).
"""
from __future__ import annotations

from apps.branding.models import WorkspaceBranding

from . import registry
from .models import UserPreference


class LockedPreferenceError(registry.PersonalizationError):
    """Raised when a caller tries to set a preference the workspace has locked."""


def _branding(workspace_id):
    return WorkspaceBranding.objects.filter(workspace_id=workspace_id).first()


def effective_locked_keys(branding) -> list:
    """Locked keys the workspace has declared, filtered to those that are actually
    lockable (accessibility/unknown keys can never be locked)."""
    raw = getattr(branding, "locked_fields", None) or []
    return [k for k in raw if registry.is_lockable(k)]


def get_user_values(workspace_id, user_id) -> dict:
    pref = UserPreference.objects.filter(workspace_id=workspace_id, user_id=user_id).first()
    return dict(pref.values) if pref and isinstance(pref.values, dict) else {}


def resolve_appearance(workspace_id, *, user_id=None, role_ids=None) -> dict:
    """Return the effective appearance settings + lock metadata for the caller."""
    branding = _branding(workspace_id)
    locked = set(effective_locked_keys(branding))
    user_values = get_user_values(workspace_id, user_id) if user_id else {}

    effective, sources = {}, {}
    for key in registry.PREFERENCE_KEYS:
        ws_default = registry.workspace_default(key, branding)
        if key in locked:
            effective[key] = ws_default
            sources[key] = "workspace_locked"
        elif key in user_values:
            effective[key] = user_values[key]
            sources[key] = "user"
        elif registry.REGISTRY[key].get("branding_field") and branding is not None:
            effective[key] = ws_default
            sources[key] = "workspace"
        else:
            effective[key] = ws_default
            sources[key] = "system"

    return {
        "appearance": effective,
        "locked": sorted(locked),
        "sources": sources,
        "allow_theme_toggle": (bool(branding.allow_theme_toggle) if branding else True),
    }


def set_user_values(workspace_id, user_id, incoming: dict) -> dict:
    """Validate + upsert a user's overrides. Locked keys are rejected (403)."""
    cleaned = registry.validate_values(incoming)
    branding = _branding(workspace_id)
    locked = set(effective_locked_keys(branding))
    blocked = sorted(k for k in cleaned if k in locked)
    if blocked:
        raise LockedPreferenceError(
            f"These preferences are locked by your administrator: {', '.join(blocked)}")
    pref, _ = UserPreference.objects.get_or_create(
        workspace_id=workspace_id, user_id=user_id, defaults={"values": {}})
    merged = dict(pref.values or {})
    merged.update(cleaned)
    pref.values = merged
    pref.save(update_fields=["values", "updated_at"])
    return pref.values


def reset_user_values(workspace_id, user_id, keys=None) -> dict:
    """Clear all overrides, or only the given keys → revert to inherited defaults."""
    pref = UserPreference.objects.filter(workspace_id=workspace_id, user_id=user_id).first()
    if pref is None:
        return {}
    if keys:
        unknown = [k for k in keys if k not in registry.PREFERENCE_KEYS]
        if unknown:
            raise registry.PersonalizationError(
                f"Unknown preference key(s): {', '.join(unknown)}")
        drop = set(keys)
        pref.values = {k: v for k, v in (pref.values or {}).items() if k not in drop}
    else:
        pref.values = {}
    pref.save(update_fields=["values", "updated_at"])
    return pref.values
