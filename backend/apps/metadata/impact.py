"""
Config-dependency impact analysis (Phase P1.4).

Answers "what will break if I delete this entity / field?" by scanning the config objects that
reference it: forms, business rules, workflows, reports, relationships, lookup + computed fields.

Structural matches (form layout membership, rule watch/action field, lookup target, relationship
endpoints) are exact. NQL/source references are best-effort substring matches and are flagged
``approximate=True`` so the UI can label them. Read-only; never mutates.
"""
from __future__ import annotations

import json
import uuid


def _dep(kind, name, detail, *, approximate=False, obj_id=None):
    return {"type": kind, "name": name, "detail": detail, "approximate": approximate,
            "id": str(obj_id) if obj_id else None}


def entity_impact(workspace_id: uuid.UUID, entity) -> list[dict]:
    """Dependents of an entity (things that reference it)."""
    from apps.metadata.models import FieldDefinition, FormDefinition
    from apps.relationships.models import RelationshipDefinition
    from apps.reporting.models import Report
    from apps.rules.models import BusinessRule
    from apps.workflows.models import WorkflowDefinition

    eid, ws = entity.id, workspace_id
    deps: list[dict] = []

    for f in FormDefinition.objects.filter(workspace_id=ws, entity_id=eid):
        deps.append(_dep("form", f.name, "Form bound to this entity", obj_id=f.id))
    for r in BusinessRule.objects.filter(workspace_id=ws, entity_id=eid):
        deps.append(_dep("rule", r.name, "Business rule on this entity", obj_id=r.id))
    for w in WorkflowDefinition.objects.filter(workspace_id=ws, entity_id=eid):
        deps.append(_dep("workflow", w.name, f"Workflow ({w.status})", obj_id=w.id))
    for rep in Report.objects.filter(workspace_id=ws):
        if str(eid) in [str(x) for x in (rep.source_entity_ids or [])]:
            deps.append(_dep("report", rep.name, "Report sources this entity", obj_id=rep.id))
    for rel in RelationshipDefinition.objects.filter(workspace_id=ws).filter(
            models_q_source_or_target(eid)):
        side = "source" if rel.source_entity_id == eid else "target"
        deps.append(_dep("relationship", rel.name, f"Relationship ({side})", obj_id=rel.id))
    # lookup fields in OTHER entities pointing at this entity
    for fd in FieldDefinition.objects.filter(
            workspace_id=ws, field_type__in=["lookup", "multi_lookup"]).exclude(entity_id=eid):
        if (fd.config or {}).get("target_entity_slug") == entity.slug:
            deps.append(_dep("lookup_field", f"{fd.entity.slug}.{fd.slug}",
                             "Lookup field targeting this entity", obj_id=fd.id))
    return deps


def field_impact(workspace_id: uuid.UUID, entity, field) -> list[dict]:
    """Dependents of a single field on an entity."""
    from apps.metadata.models import FieldDefinition, FormDefinition
    from apps.reporting.models import Report
    from apps.rules.models import BusinessRule

    eid, ws, slug = entity.id, workspace_id, field.slug
    deps: list[dict] = []

    # Forms that place the field (exact: layout section field-slug membership)
    for f in FormDefinition.objects.filter(workspace_id=ws, entity_id=eid):
        if any(slug in (sec.get("fields") or []) for sec in (f.layout or [])):
            deps.append(_dep("form", f.name, "Field placed on this form", obj_id=f.id))

    # Rules on this entity: watched / set-by-action (exact) or in condition (approximate)
    for r in BusinessRule.objects.filter(workspace_id=ws, entity_id=eid):
        why = []
        if r.watch_field_slug == slug:
            why.append("watched")
        if any((a or {}).get("field") == slug for a in (r.actions or [])):
            why.append("set by action")
        approx = False
        if r.condition_nql and slug in r.condition_nql:
            why.append("referenced in condition")
            approx = not why[:-1]  # approximate only if the *sole* reason is the text match
        if why:
            deps.append(_dep("rule", r.name, ", ".join(why), approximate=approx, obj_id=r.id))

    # Computed/rollup fields whose config references this field (exact-ish: JSON contains slug)
    for fd in FieldDefinition.objects.filter(
            workspace_id=ws, entity_id=eid, field_type__in=["formula", "rollup"]).exclude(slug=slug):
        if slug in json.dumps(fd.config or {}):
            deps.append(_dep("computed_field", fd.slug, f"{fd.field_type} references this field", obj_id=fd.id))

    # Reports sourcing this entity whose NQL text mentions the field (approximate)
    for rep in Report.objects.filter(workspace_id=ws):
        if str(eid) in [str(x) for x in (rep.source_entity_ids or [])] and rep.nql_source and slug in rep.nql_source:
            deps.append(_dep("report", rep.name, "Referenced in report query", approximate=True, obj_id=rep.id))

    return deps


def models_q_source_or_target(entity_id):
    """Q(source_entity_id=e) | Q(target_entity_id=e) — kept here to avoid a top-level django import."""
    from django.db.models import Q
    return Q(source_entity_id=entity_id) | Q(target_entity_id=entity_id)


# ── P2.14 extension: dependents of the remaining config object types ─────────
# impact.py is the SINGLE system of record for dependency DISCOVERY ("what references X?").
# apps/dependency orchestrates these (graph/risk/promotion); it never re-discovers.

def report_impact(workspace_id, report_id) -> list[dict]:
    """Dashboards whose widgets/layout use a report."""
    from apps.reporting.models import Dashboard, DashboardWidget
    ws, deps = workspace_id, []
    dash_ids = set(DashboardWidget.objects.filter(
        workspace_id=ws, report_id=report_id).values_list("dashboard_id", flat=True))
    for d in Dashboard.objects.filter(workspace_id=ws, id__in=dash_ids):
        deps.append(_dep("dashboard", d.name, "Dashboard widget uses this report", obj_id=d.id))
    for d in Dashboard.objects.filter(workspace_id=ws).exclude(id__in=dash_ids):
        if str(report_id) in str(d.layout or []):
            deps.append(_dep("dashboard", d.name, "Dashboard references this report",
                             approximate=True, obj_id=d.id))
    return deps


def dashboard_impact(workspace_id, dashboard_id) -> list[dict]:
    """Navigation items linking to a dashboard."""
    from apps.studio.models import Navigation
    deps = []
    for nav in Navigation.objects.filter(workspace_id=workspace_id):
        if str(dashboard_id) in str(nav.tree or []):
            deps.append(_dep("navigation", nav.name, "Navigation links to this dashboard",
                             approximate=True, obj_id=nav.id))
    return deps


def kpi_impact(workspace_id, kpi_id) -> list[dict]:
    """Snapshots + dashboards referencing a KPI by code."""
    from apps.analytics.models import KPIDefinition, KPISnapshot
    from apps.reporting.models import Dashboard
    kpi = KPIDefinition.objects.filter(workspace_id=workspace_id, id=kpi_id).first()
    if kpi is None:
        return []
    deps = []
    snaps = KPISnapshot.objects.filter(workspace_id=workspace_id, code=kpi.code).count()
    if snaps:
        deps.append(_dep("kpi_snapshot", kpi.code, f"{snaps} historical snapshot(s)"))
    for d in Dashboard.objects.filter(workspace_id=workspace_id):
        if kpi.code in str(d.layout or ""):
            deps.append(_dep("dashboard", d.name, "Dashboard references this KPI",
                             approximate=True, obj_id=d.id))
    return deps


def role_impact(workspace_id, role_id) -> list[dict]:
    """Permissions, field permissions, member assignments and child roles for a role."""
    from apps.permissions.models import FieldPermission, Permission, Role
    role = Role.objects.filter(workspace_id=workspace_id, id=role_id).first()
    if role is None:
        return []
    deps = []
    perms = Permission.objects.filter(workspace_id=workspace_id, role_id=role_id).count()
    if perms:
        deps.append(_dep("permission", role.name, f"{perms} permission grant(s)"))
    fperms = FieldPermission.objects.filter(workspace_id=workspace_id, role_id=role_id).count()
    if fperms:
        deps.append(_dep("field_permission", role.name, f"{fperms} field permission(s)"))
    children = Role.objects.filter(workspace_id=workspace_id, parent_role_id=role_id).count()
    if children:
        deps.append(_dep("role", role.name, f"{children} child role(s) inherit this"))
    return deps


def view_impact(workspace_id, view_id) -> list[dict]:
    """Personal saved-view customizations of a view definition."""
    from apps.views_saved.models import SavedView
    return [_dep("saved_view", sv.name or "personal", "Personal view customization", obj_id=sv.id)
            for sv in SavedView.objects.filter(workspace_id=workspace_id, view_definition_id=view_id)]


def _leaf_impact(workspace_id, object_id) -> list[dict]:
    """Workflows / rules / forms are typically leaves (nothing else references them)."""
    return []


# object_type → (model, discovery scanner). The SINGLE registry of dependency discovery.
def _registry():
    from apps.analytics.models import KPIDefinition
    from apps.metadata.models import (
        EntityDefinition,
        FieldDefinition,
        FormDefinition,
        ViewDefinition,
    )
    from apps.permissions.models import Role
    from apps.reporting.models import Dashboard, Report
    from apps.rules.models import BusinessRule
    from apps.workflows.models import WorkflowDefinition

    def entity_scan(ws, oid):
        e = EntityDefinition.objects.filter(workspace_id=ws, id=oid).first()
        return entity_impact(ws, e) if e else []

    def field_scan(ws, oid):
        f = FieldDefinition.objects.filter(
            workspace_id=ws, id=oid).select_related("entity").first()
        return field_impact(ws, f.entity, f) if f else []

    return {
        "entity": (EntityDefinition, entity_scan),
        "field": (FieldDefinition, field_scan),
        "report": (Report, report_impact),
        "dashboard": (Dashboard, dashboard_impact),
        "kpi": (KPIDefinition, kpi_impact),
        "role": (Role, role_impact),
        "view": (ViewDefinition, view_impact),
        "workflow": (WorkflowDefinition, _leaf_impact),
        "rule": (BusinessRule, _leaf_impact),
        "form": (FormDefinition, _leaf_impact),
    }


_REGISTRY: dict = {}

OBJECT_TYPES = ["entity", "field", "report", "dashboard", "kpi", "role", "view",
                "workflow", "rule", "form"]

# A dependent ``type`` (as emitted by a scanner) → the object_type to recurse into when building a
# dependency graph. Lives HERE (the discovery SOR) so all dependency-type knowledge is in one place;
# graph traversal in apps/dependency reads it but never defines dependency types.
RECURSE_TYPE = {
    "report": "report", "dashboard": "dashboard", "role": "role", "form": "form",
    "workflow": "workflow", "rule": "rule", "saved_view": "view",
    "lookup_field": "field", "computed_field": "field",
}


def _reg():
    if not _REGISTRY:
        _REGISTRY.update(_registry())
    return _REGISTRY


def dependents(workspace_id, object_type: str, object_id) -> list[dict]:
    """THE discovery dispatch: all config objects that depend on the given object."""
    entry = _reg().get(object_type)
    return entry[1](workspace_id, object_id) if entry else []


def resolve_name(workspace_id, object_type: str, object_id) -> str:
    entry = _reg().get(object_type)
    if entry is None:
        return str(object_id)
    obj = entry[0].objects.filter(workspace_id=workspace_id, id=object_id).first()
    if obj is None:
        return str(object_id)
    return (getattr(obj, "name", None) or getattr(obj, "slug", None)
            or getattr(obj, "code", None) or str(object_id))
