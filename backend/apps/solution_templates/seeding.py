"""
System solution seeding (Phase P2.4A).

Composes ready-to-install ``SolutionTemplate`` rows from the standard library so Sridhar ERP
ships complete solutions out-of-the-box. Idempotent: upserts by slug. Called from data
migration 0003 and the ``seed_solutions`` management command; tests call it directly.
"""
from __future__ import annotations

from .library import business_objects as bo
from .library.dashboards import DASHBOARD_LIBRARY
from .library.reports import report_set
from .library.roles import ROLE_LIBRARY
from .library.workflows import WORKFLOW_LIBRARY


def _form_for(entity_slug: str, name: str) -> dict:
    obj = bo.BUSINESS_OBJECTS[entity_slug]
    return {
        "slug": f"{entity_slug}_form", "entity_slug": entity_slug, "name": name,
        "is_default": True,
        "layout": [{"section": "Details",
                    "fields": [f["slug"] for f in obj["fields"]]}],
    }


def build_sales_crm_manifest() -> dict:
    """A complete Sales CRM solution exercising every applier (entities/forms/views/
    workflows/reports/notification_templates/roles/dashboards/studio)."""
    entities = [bo.BUSINESS_OBJECTS[s] for s in ("customer", "contact", "sales_order")]
    return {
        "schema_version": 1,
        "entities": entities,
        "forms": [
            _form_for("customer", "Customer"),
            _form_for("contact", "Contact"),
            _form_for("sales_order", "Sales Order"),
        ],
        "views": [
            {"slug": "customer_table", "entity_slug": "customer", "name": "All Customers",
             "view_type": "table", "is_default": True},
            {"slug": "so_pipeline", "entity_slug": "sales_order", "name": "Pipeline",
             "view_type": "kanban", "config": {"group_by": "status"}},
        ],
        "workflows": [{**WORKFLOW_LIBRARY["approval"], "slug": "so_approval",
                       "name": "Sales Order Approval", "entity_slug": "sales_order"}],
        "reports": report_set("customer"),
        "notification_templates": [
            {"slug": "approval_requested", "name": "Approval Requested",
             "channels": ["in_app"], "subject_template": "Approval needed",
             "body_template": "A record needs your approval."},
        ],
        "roles": [ROLE_LIBRARY["administrator"], ROLE_LIBRARY["manager"], ROLE_LIBRARY["user"]],
        "dashboards": [DASHBOARD_LIBRARY["executive"], DASHBOARD_LIBRARY["operational"],
                       DASHBOARD_LIBRARY["analytical"]],
        "navigations": [{
            "ref": "main", "name": "CRM Menu", "scope": "app",
            "tree": [{"label": "Sales", "items": [
                {"label": "Customers", "type": "entity", "target": "customer"},
                {"label": "Contacts", "type": "entity", "target": "contact"},
                {"label": "Sales Orders", "type": "entity", "target": "sales_order"},
            ]}],
        }],
        "home_layouts": [{
            "ref": "home", "name": "CRM Home", "scope": "app",
            "widgets": [{"type": "card", "title": "Welcome to your CRM"}],
        }],
        "applications": [{
            "slug": "sales_crm", "name": "Sales CRM", "icon": "Users", "color": "#2563eb",
            "included_entity_slugs": ["customer", "contact", "sales_order"],
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": ["administrator", "manager", "user"], "is_published": True,
        }],
    }


SYSTEM_TEMPLATES = [
    {"slug": "sales_crm", "name": "Sales CRM", "category": "CRM",
     "description": "Customers, contacts and a sales-order pipeline with approval, "
                    "dashboards, reports and roles — ready to use.",
     "icon": "Users", "color": "#2563eb", "builder": build_sales_crm_manifest},
]


def seed_system_templates() -> list:
    """Upsert the shipped system solutions. Returns the SolutionTemplate rows."""
    from .models import SolutionTemplate
    rows = []
    for spec in SYSTEM_TEMPLATES:
        manifest = spec["builder"]()
        tpl, _ = SolutionTemplate.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"], "category": spec["category"],
                "description": spec["description"], "icon": spec.get("icon", ""),
                "color": spec.get("color", ""), "publisher": "Sridhar ERP",
                "version": "1.0.0", "manifest": manifest,
                "is_system": True, "is_published": True,
            })
        rows.append(tpl)
    return rows
