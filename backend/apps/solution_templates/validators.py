"""
Solution-manifest validation (Phase P2.4A).

Reuses ``marketplace.validators.validate_manifest`` for the shared sections (entities/
workflows/rules/reports/notification_templates/permissions, plus schema_version + size cap)
and adds checks for the sections unique to solutions: forms, views, roles, dashboards,
applications, navigations, home_layouts. Pure — no DB writes; empty list ⇒ valid.
"""
from __future__ import annotations

import re

from apps.marketplace.validators import validate_manifest as _validate_core

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VIEW_TYPES = {"table", "kanban", "calendar", "gantt", "gallery", "map", "timeline", "form"}


def _check_slugs(errors, section, items, *, key="slug"):
    seen = set()
    for i, it in enumerate(items or []):
        if not isinstance(it, dict):
            errors.append(f"{section}[{i}] must be an object")
            continue
        slug = it.get(key)
        if not slug or not SLUG_RE.match(str(slug)) or len(str(slug)) > 63:
            errors.append(f"{section}[{i}].{key} '{slug}' is not a valid slug")
        elif slug in seen:
            errors.append(f"{section} duplicate {key} '{slug}'")
        else:
            seen.add(slug)


def validate_solution_manifest(manifest) -> list[str]:
    errors = list(_validate_core(manifest))
    if not isinstance(manifest, dict):
        return errors or ["manifest must be an object"]

    _check_slugs(errors, "forms", manifest.get("forms"))
    for i, fm in enumerate(manifest.get("forms", []) or []):
        if isinstance(fm, dict) and not fm.get("entity_slug"):
            errors.append(f"forms[{i}] requires entity_slug")

    _check_slugs(errors, "views", manifest.get("views"))
    for i, vw in enumerate(manifest.get("views", []) or []):
        if not isinstance(vw, dict):
            continue
        if not vw.get("entity_slug"):
            errors.append(f"views[{i}] requires entity_slug")
        vt = vw.get("view_type", "table")
        if vt not in VIEW_TYPES:
            errors.append(f"views[{i}].view_type '{vt}' is invalid")

    _check_slugs(errors, "roles", manifest.get("roles"))
    _check_slugs(errors, "dashboards", manifest.get("dashboards"))
    _check_slugs(errors, "applications", manifest.get("applications"))

    # Standard-engine sections (Phase P3.1A). All optional; validated only when present.
    _check_slugs(errors, "document_templates", manifest.get("document_templates"))
    _check_slugs(errors, "email_templates", manifest.get("email_templates"))
    _check_slugs(errors, "approval_processes", manifest.get("approval_processes"))
    for i, ap in enumerate(manifest.get("approval_processes", []) or []):
        if isinstance(ap, dict) and not ap.get("entity_slug"):
            errors.append(f"approval_processes[{i}] requires entity_slug")
    _check_slugs(errors, "sla_policies", manifest.get("sla_policies"))
    for i, sp in enumerate(manifest.get("sla_policies", []) or []):
        if isinstance(sp, dict) and not sp.get("entity_slug"):
            errors.append(f"sla_policies[{i}] requires entity_slug")
    _check_slugs(errors, "kpis", manifest.get("kpis"), key="code")
    for i, g in enumerate(manifest.get("portal_grants", []) or []):
        if not isinstance(g, dict):
            errors.append(f"portal_grants[{i}] must be an object")
            continue
        if not g.get("entity_slug"):
            errors.append(f"portal_grants[{i}] requires entity_slug")
        if not g.get("link_field"):
            errors.append(f"portal_grants[{i}] requires link_field")
    for i, bh in enumerate(manifest.get("business_hours", []) or []):
        if isinstance(bh, dict) and not bh.get("name"):
            errors.append(f"business_hours[{i}] requires name")

    return errors
