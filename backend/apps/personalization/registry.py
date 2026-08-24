"""
Personalization preference registry (Phase P0).

Declarative catalogue of user-settable appearance/accessibility preferences —
mirrors the ERP's existing registry pattern (field-type / NQL registries). It is the
single source of truth for *what preferences exist*, and it governs validation
(unknown keys rejected), defaults, workspace-default inheritance, and lockability.

Each entry declares:
  type            enum | bool | int | color
  values/min/max  allowed set or numeric range
  default         system default (lowest precedence)
  branding_field  WorkspaceBranding attribute that supplies the *workspace* default
                  (None → use ``default``)
  lockable        admins may pin the key via WorkspaceBranding.locked_fields
  accessibility   accessibility right → **never lockable** (WCAG: a user may always
                  adjust contrast / motion / text size)

This module imports nothing from other apps, so lower-level apps (e.g. branding)
may reference it without a circular import.
"""
from __future__ import annotations

import re

ENUM = "enum"
BOOL = "bool"
INT = "int"
COLOR = "color"

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class PersonalizationError(Exception):  # noqa: N818 — domain error
    pass


REGISTRY: dict[str, dict] = {
    "theme": {
        "type": ENUM, "values": ["light", "dark", "system"],
        "branding_field": "default_theme", "default": "system",
        "lockable": True, "accessibility": False,
    },
    "accent": {
        "type": COLOR, "branding_field": "color_accent", "default": "#06b6d4",
        "lockable": True, "accessibility": False,
    },
    "density": {
        "type": ENUM, "values": ["comfortable", "compact"],
        "branding_field": "ui_density", "default": "comfortable",
        "lockable": True, "accessibility": False,
    },
    "radius": {
        "type": ENUM, "values": ["none", "sm", "md", "lg", "xl"],
        "branding_field": "border_radius", "default": "md",
        "lockable": True, "accessibility": False,
    },
    "font_scale": {
        "type": INT, "min": 80, "max": 150,
        "branding_field": None, "default": 100,
        "lockable": False, "accessibility": True,
    },
    "high_contrast": {
        "type": BOOL, "branding_field": None, "default": False,
        "lockable": False, "accessibility": True,
    },
    "reduced_motion": {
        "type": ENUM, "values": ["system", "on", "off"],
        "branding_field": None, "default": "system",
        "lockable": False, "accessibility": True,
    },
}

PREFERENCE_KEYS = frozenset(REGISTRY)
LOCKABLE_KEYS = frozenset(k for k, v in REGISTRY.items() if v["lockable"])
ACCESSIBILITY_KEYS = frozenset(k for k, v in REGISTRY.items() if v["accessibility"])


def is_lockable(key: str) -> bool:
    return key in LOCKABLE_KEYS


def coerce_value(key: str, value):
    """Validate + coerce a single preference value; raise on invalid input."""
    if key not in REGISTRY:
        raise PersonalizationError(f"Unknown preference key: {key!r}")
    spec = REGISTRY[key]
    t = spec["type"]
    if t == ENUM:
        if value not in spec["values"]:
            raise PersonalizationError(f"{key} must be one of {spec['values']}")
        return value
    if t == BOOL:
        if not isinstance(value, bool):
            raise PersonalizationError(f"{key} must be a boolean")
        return value
    if t == INT:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PersonalizationError(f"{key} must be an integer")
        if not (spec["min"] <= value <= spec["max"]):
            raise PersonalizationError(f"{key} must be between {spec['min']} and {spec['max']}")
        return value
    if t == COLOR:
        if not isinstance(value, str) or not _HEX_RE.match(value):
            raise PersonalizationError(f"{key} must be a hex colour like #06b6d4")
        return value
    raise PersonalizationError(f"Unsupported type for {key}")  # pragma: no cover — guarded by REGISTRY


def validate_values(values: dict) -> dict:
    """Validate an incoming override map; returns a cleaned copy or raises."""
    if not isinstance(values, dict):
        raise PersonalizationError("preferences must be an object")
    return {k: coerce_value(k, v) for k, v in values.items()}


def system_default(key: str):
    return REGISTRY[key]["default"]


def workspace_default(key: str, branding):
    """Workspace-level default for a key: the WorkspaceBranding field if present,
    else the registry system default."""
    spec = REGISTRY[key]
    field = spec.get("branding_field")
    if field and branding is not None:
        val = getattr(branding, field, None)
        if val not in (None, ""):
            return val
    return spec["default"]


def public_catalogue() -> dict:
    """Registry shape for the UI (drives the Appearance page controls)."""
    return {
        k: {
            "type": v["type"],
            "values": v.get("values"),
            "min": v.get("min"),
            "max": v.get("max"),
            "default": v["default"],
            "lockable": v["lockable"],
            "accessibility": v["accessibility"],
        }
        for k, v in REGISTRY.items()
    }
