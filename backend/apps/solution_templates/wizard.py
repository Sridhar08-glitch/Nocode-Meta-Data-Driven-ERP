"""
Create Solution Wizard (Phase P2.4B).

The customer-facing entry point for building an ERP solution. It is a THIN composer over the
P2.4A framework: it turns a wizard selection (solution type / industry preset / chosen library
building blocks / config) into a standard solution manifest, resolves dependencies, validates,
previews (with collision warnings), and installs through the SAME authoritative installer
(``services._install_manifest``). There is no separate provisioning path — the installer stays
the single source of truth. Audit events: solution.wizard.previewed / .created / .failed.
"""
from __future__ import annotations

import re
import uuid

from apps.eventstore.events import DomainEventData, DomainEventFactory

from . import services
from .library.business_objects import BUSINESS_OBJECTS
from .library.dashboards import DASHBOARD_LIBRARY
from .library.reports import report_set
from .library.roles import ROLE_LIBRARY
from .library.workflows import WORKFLOW_LIBRARY
from .validators import validate_solution_manifest

# Which library workflows imply the approval-request notification template.
_APPROVAL_WORKFLOWS = {"approval", "review", "hiring", "procurement_approval", "invoice_approval"}
# Map a short report key → the report_set slug it produces.
_REPORT_KEY_TO_SLUG = {
    "summary": "summary_report", "detail": "detail_report", "trend": "trend_report",
    "aging": "aging_report", "kpi": "kpi_report",
}


# ── built-in solution types (recommend library building blocks) ──────────────
def _rec(objects, workflows, roles, dashboards, reports):
    return {"business_objects": objects, "workflows": workflows, "roles": roles,
            "dashboards": dashboards, "reports": reports}


SOLUTION_TYPES: dict[str, dict] = {
    "crm": {"label": "CRM", "recommends": _rec(
        ["customer", "contact", "sales_order"], ["approval", "assignment"],
        ["administrator", "manager", "user"], ["executive", "operational"],
        ["summary", "detail", "trend", "kpi"])},
    "hr": {"label": "HR", "recommends": _rec(
        ["employee", "task"], ["hiring", "onboarding", "offboarding", "approval"],
        ["administrator", "manager", "user"], ["operational"], ["summary", "detail"])},
    "procurement": {"label": "Procurement", "recommends": _rec(
        ["vendor", "purchase_order", "product"], ["procurement_approval", "approval"],
        ["administrator", "manager", "approver"], ["operational", "analytical"],
        ["summary", "aging"])},
    "inventory": {"label": "Inventory", "recommends": _rec(
        ["product", "warehouse"], ["approval"], ["administrator", "manager", "user"],
        ["operational"], ["summary", "detail"])},
    "projects": {"label": "Projects", "recommends": _rec(
        ["project", "task"], ["assignment", "review"], ["administrator", "manager", "user"],
        ["operational"], ["summary", "detail"])},
    "assets": {"label": "Assets", "recommends": _rec(
        ["asset"], ["review", "approval"], ["administrator", "manager", "auditor"],
        ["analytical"], ["summary", "detail"])},
    "helpdesk": {"label": "Helpdesk", "recommends": _rec(
        ["ticket", "customer", "contact"], ["assignment", "escalation"],
        ["administrator", "manager", "user"], ["operational"], ["summary", "trend"])},
    "custom": {"label": "Custom", "recommends": _rec([], [], [], [], [])},
}


# ── industry presets (recommend across types) ────────────────────────────────
INDUSTRY_PRESETS: dict[str, dict] = {
    "retail": {"label": "Retail", "recommends": _rec(
        ["customer", "product", "warehouse", "vendor", "purchase_order", "ticket"],
        ["procurement_approval", "assignment"], ["administrator", "manager", "user"],
        ["executive", "operational"], ["summary", "trend", "aging"])},
    "manufacturing": {"label": "Manufacturing", "recommends": _rec(
        ["product", "warehouse", "vendor", "purchase_order", "asset", "project"],
        ["procurement_approval", "review"], ["administrator", "manager", "approver"],
        ["operational", "analytical"], ["summary", "detail"])},
    "construction": {"label": "Construction", "recommends": _rec(
        ["project", "task", "vendor", "purchase_order", "asset", "contract"],
        ["approval", "assignment"], ["administrator", "manager", "approver"],
        ["operational"], ["summary", "detail"])},
    "healthcare": {"label": "Healthcare", "recommends": _rec(
        ["patient", "practitioner", "appointment", "medical_record", "invoice"],
        ["assignment", "review"], ["administrator", "manager", "user"],
        ["operational"], ["summary", "detail"])},
    "professional_services": {"label": "Professional Services", "recommends": _rec(
        ["customer", "contact", "project", "task", "contract", "invoice"],
        ["approval", "assignment"], ["administrator", "manager", "user"],
        ["executive", "operational"], ["summary", "trend"])},
    "education": {"label": "Education", "recommends": _rec(
        ["contact", "project", "task", "contract"], ["assignment", "review"],
        ["administrator", "manager", "user"], ["operational"], ["summary", "detail"])},
    "finance": {"label": "Finance", "recommends": _rec(
        ["customer", "contact", "invoice", "contract"], ["approval", "review"],
        ["administrator", "manager", "auditor"], ["executive", "analytical"],
        ["summary", "aging", "kpi"])},
    "logistics": {"label": "Logistics", "recommends": _rec(
        ["customer", "product", "warehouse", "vendor", "purchase_order"],
        ["procurement_approval", "assignment"], ["administrator", "manager", "user"],
        ["operational"], ["summary", "trend"])},
    "general_business": {"label": "General Business", "recommends": _rec(
        ["customer", "contact", "task", "invoice"], ["approval", "assignment"],
        ["administrator", "manager", "user"], ["executive", "operational"],
        ["summary", "detail"])},
}


def slugify(value: str) -> str:
    """Underscore slug matching the manifest slug rule ^[a-z][a-z0-9_]*$."""
    s = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    if not s:
        s = "solution"
    if not s[0].isalpha():
        s = "s_" + s
    return s[:63]


def options() -> dict:
    """Everything the wizard UI needs to render its choices."""
    from .library import get_library
    return {
        "solution_types": [
            {"key": k, "label": v["label"], "recommends": v["recommends"]}
            for k, v in SOLUTION_TYPES.items()],
        "industries": [
            {"key": k, "label": v["label"], "recommends": v["recommends"]}
            for k, v in INDUSTRY_PRESETS.items()],
        "library": get_library(),
    }


# ── dependency resolution ────────────────────────────────────────────────────
def resolve_dependencies(object_slugs) -> list[str]:
    """Return the selected business objects PLUS every object they reference through a
    ``lookup`` field (recursively) — so users never resolve dependencies by hand."""
    result: list[str] = []
    seen: set[str] = set()
    queue = list(object_slugs or [])
    while queue:
        slug = queue.pop(0)
        if slug in seen or slug not in BUSINESS_OBJECTS:
            continue
        seen.add(slug)
        result.append(slug)
        for fd in BUSINESS_OBJECTS[slug].get("fields", []):
            if fd.get("field_type") == "lookup":
                target = (fd.get("config") or {}).get("target_entity_slug")
                if target and target not in seen:
                    queue.append(target)
    return result


# ── manifest composition ─────────────────────────────────────────────────────
def _form_for(entity_slug: str) -> dict:
    obj = BUSINESS_OBJECTS[entity_slug]
    return {"slug": f"{entity_slug}_form", "entity_slug": entity_slug,
            "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details",
                        "fields": [f["slug"] for f in obj["fields"]]}]}


def _view_for(entity_slug: str) -> dict:
    obj = BUSINESS_OBJECTS[entity_slug]
    has_status = any(f["slug"] == "status" for f in obj["fields"])
    view = {"slug": f"{entity_slug}_table", "entity_slug": entity_slug,
            "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}
    return view if not has_status else view


def _to_keys(library: dict, selected) -> list[str]:
    """Normalise a selection list to canonical library KEYS, accepting either the key or the
    entry's ``slug`` (e.g. dashboards: key ``executive`` vs slug ``executive_dashboard``). The
    frontend may send either; both resolve to the same building block."""
    slug_to_key = {v.get("slug"): k for k, v in library.items()}
    keys: list[str] = []
    for s in selected or []:
        if s in library:
            keys.append(s)
        elif s in slug_to_key:
            keys.append(slug_to_key[s])
    return keys


def build_manifest(selection: dict) -> dict:
    """Compose a standard solution manifest from a wizard selection."""
    cfg = selection.get("config", {}) or {}
    app_name = cfg.get("application_name") or cfg.get("solution_name") or "My Solution"
    app_slug = slugify(app_name)

    objects = resolve_dependencies(selection.get("business_objects", []))
    entities = [BUSINESS_OBJECTS[s] for s in objects if s in BUSINESS_OBJECTS]
    primary = objects[0] if objects else None

    forms = [_form_for(s) for s in objects]
    views = [_view_for(s) for s in objects]

    workflow_keys = _to_keys(WORKFLOW_LIBRARY, selection.get("workflows"))
    workflows = []
    for key in workflow_keys:
        tmpl = WORKFLOW_LIBRARY[key]
        if primary is None:
            continue
        workflows.append({**tmpl, "slug": f"{app_slug}_{key}",
                          "name": f"{tmpl['name']} ({BUSINESS_OBJECTS[primary]['name']})",
                          "entity_slug": primary})

    reports = []
    if primary is not None:
        # Accept either the short report key (summary) or its slug (summary_report).
        wanted = {_REPORT_KEY_TO_SLUG.get(k, k) for k in (selection.get("reports") or [])}
        reports = [r for r in report_set(primary) if r["slug"] in wanted]

    roles = [ROLE_LIBRARY[k] for k in _to_keys(ROLE_LIBRARY, selection.get("roles"))]

    dashboards = [DASHBOARD_LIBRARY[k]
                  for k in _to_keys(DASHBOARD_LIBRARY, selection.get("dashboards"))]

    notification_templates = []
    if any(k in _APPROVAL_WORKFLOWS for k in workflow_keys):
        notification_templates.append({
            "slug": "approval_requested", "name": "Approval Requested",
            "channels": ["in_app"], "subject_template": "Approval needed",
            "body_template": "A record needs your approval."})

    nav_items = [{"label": BUSINESS_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                 for s in objects]
    navigations = [{"ref": "main", "name": f"{app_name} Menu", "scope": "app",
                    "tree": [{"label": app_name, "items": nav_items}]}]
    home_layouts = [{"ref": "home", "name": f"{app_name} Home", "scope": "app",
                     "widgets": [{"type": "card", "title": f"Welcome to {app_name}"}]}]
    applications = [{
        "slug": app_slug, "name": app_name,
        "description": cfg.get("description", ""),
        "icon": cfg.get("icon", ""), "color": cfg.get("color", ""),
        "included_entity_slugs": objects, "navigation_ref": "main",
        "home_layout_ref": "home",
        "role_slugs": [r["slug"] for r in roles], "is_published": True,
    }]

    return {
        "schema_version": 1, "entities": entities, "forms": forms, "views": views,
        "workflows": workflows, "reports": reports,
        "notification_templates": notification_templates, "roles": roles,
        "dashboards": dashboards, "navigations": navigations,
        "home_layouts": home_layouts, "applications": applications,
    }


# ── audit ────────────────────────────────────────────────────────────────────
def _emit(workspace_id, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="solution_wizard").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="solution_wizard", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _summary(manifest) -> dict:
    keys = ["entities", "forms", "views", "workflows", "reports",
            "notification_templates", "roles", "dashboards", "applications"]
    return {k: len(manifest.get(k, []) or []) for k in keys}


# ── preview + create ─────────────────────────────────────────────────────────
def preview(selection: dict, *, workspace_id, actor_id=None) -> dict:
    from apps.metadata.models import EntityDefinition
    from apps.studio.models import Application

    manifest = build_manifest(selection)
    errors = validate_solution_manifest(manifest)

    requested = list(selection.get("business_objects", []) or [])
    resolved = [e["slug"] for e in manifest["entities"]]
    added = [s for s in resolved if s not in requested]

    warnings: list[str] = []
    if added:
        warnings.append("Auto-included dependencies: " + ", ".join(added))
    existing = set(EntityDefinition.objects.filter(
        workspace_id=workspace_id, slug__in=resolved).values_list("slug", flat=True))
    for slug in sorted(existing):
        warnings.append(f"Object '{slug}' already exists — it will be extended, not replaced.")
    app_slug = manifest["applications"][0]["slug"] if manifest["applications"] else None
    if app_slug and Application.objects.filter(
            workspace_id=workspace_id, slug=app_slug).exists():
        warnings.append(f"Application '{app_slug}' already exists — it will be skipped.")
    if not resolved:
        warnings.append("No business objects selected — nothing of substance will be created.")

    result = {
        "valid": not errors, "errors": errors, "warnings": warnings,
        "resolved_objects": resolved, "summary": _summary(manifest), "manifest": manifest,
    }
    _emit(workspace_id, workspace_id, "solution.wizard.previewed",
          {"summary": result["summary"], "warnings": warnings}, actor_id)
    return result


def create(selection: dict, *, workspace_id, actor_id):
    cfg = selection.get("config", {}) or {}
    solution_name = cfg.get("solution_name") or cfg.get("application_name") or "My Solution"
    manifest = build_manifest(selection)
    errors = validate_solution_manifest(manifest)
    if errors:
        _emit(workspace_id, workspace_id, "solution.wizard.failed",
              {"errors": errors}, actor_id)
        raise services.SolutionTemplateError(f"Invalid manifest: {'; '.join(errors)}")
    try:
        installed = services._install_manifest(
            manifest=manifest, workspace_id=workspace_id, installed_by=actor_id,
            solution_slug=slugify(solution_name), solution_name=solution_name)
    except Exception as exc:  # noqa: BLE001
        _emit(workspace_id, workspace_id, "solution.wizard.failed",
              {"error": str(exc)}, actor_id)
        raise services.SolutionTemplateError(f"Provisioning failed: {exc}") from exc
    _emit(workspace_id, installed.id, "solution.wizard.created",
          {"solution_slug": installed.solution_slug, "summary": installed.summary}, actor_id)
    return installed
