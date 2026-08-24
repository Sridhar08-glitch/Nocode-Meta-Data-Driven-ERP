"""
Enterprise Analytics Solution blueprint (Phase P2.13).

Analytics is native (the KPI Registry + cross-module evaluators), so — like Payroll/Manufacturing —
the SolutionTemplate provisions the framework-expressible surface: the analytics Roles + the
Application/Navigation/Home that surface the native ``/analytics`` UI (executive scorecards, KPI
cards, ERP health). Reports/dashboards/exports are REUSED from the existing reporting engine.
Installable from the Solution Catalog and the Create Solution Wizard.
"""
from __future__ import annotations


def _role(slug, name, description):
    return {"slug": slug, "name": name, "description": description, "permissions": []}


ANALYTICS_ROLES = [
    _role("analytics_administrator", "Analytics Administrator", "Manage the KPI registry."),
    _role("executive_ceo", "CEO", "Executive scorecard."),
    _role("executive_cfo", "CFO", "Financial scorecard."),
    _role("executive_coo", "COO", "Operations scorecard."),
    _role("executive_chro", "CHRO", "People scorecard."),
    _role("executive_cio", "CIO", "IT/service scorecard."),
]

_NAV_ITEMS = [
    {"label": "Analytics Home", "type": "internal", "target": "/analytics"},
    {"label": "KPI Registry", "type": "internal", "target": "/analytics/kpis"},
    {"label": "Scorecards", "type": "internal", "target": "/analytics/scorecards"},
    {"label": "ERP Health", "type": "internal", "target": "/analytics/health"},
]


def build_analytics_manifest() -> dict:
    return {
        "schema_version": 1,
        "roles": ANALYTICS_ROLES,
        "navigations": [{
            "ref": "main", "name": "Analytics Menu", "scope": "app",
            "tree": [{"label": "Analytics", "items": _NAV_ITEMS}],
        }],
        "home_layouts": [{"ref": "home", "name": "Analytics Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Analytics & KPIs"}]}],
        "applications": [{
            "slug": "analytics", "name": "Analytics & Intelligence", "icon": "BarChart3",
            "color": "#0f766e", "included_entity_slugs": [], "navigation_ref": "main",
            "home_layout_ref": "home", "role_slugs": [r["slug"] for r in ANALYTICS_ROLES],
            "is_published": True,
        }],
    }


def seed_analytics_template():
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="analytics",
        defaults={
            "name": "Analytics & Intelligence",
            "category": "Analytics",
            "description": "Enterprise reporting, analytics and executive intelligence — a "
                           "centralized KPI registry, role-based executive scorecards (CEO/CFO/COO/"
                           "CHRO/CIO), cross-module KPIs, thresholds + alerts, KPI snapshots and ERP "
                           "health. Reuses the existing reporting/dashboard/export/scheduler engines.",
            "icon": "BarChart3", "color": "#0f766e", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_analytics_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
