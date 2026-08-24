"""
Manufacturing Solution blueprint (Phase P2.12).

Manufacturing is a NATIVE engine (BOM/MRP/costing/scheduling/OEE), so — like Payroll — its data/
dashboards/reports are native, not framework metadata. The SolutionTemplate provisions the
framework-expressible surface: the manufacturing Roles + the Application/Navigation/Home that
surface the native ``/manufacturing`` UI (navigation uses ``internal`` links). Installable from the
Solution Catalog and the Create Solution Wizard.
"""
from __future__ import annotations


def _role(slug, name, description):
    return {"slug": slug, "name": name, "description": description, "permissions": []}


MANUFACTURING_ROLES = [
    _role("manufacturing_manager", "Manufacturing Manager", "Full manufacturing control."),
    _role("production_planner", "Production Planner", "MRP, BOMs and scheduling."),
    _role("production_supervisor", "Production Supervisor", "Shop-floor execution."),
    _role("mfg_operator", "Operator", "Operate work centers."),
    _role("quality_inspector", "Quality Inspector", "Quality checks and NCR."),
    _role("maintenance_planner", "Maintenance Planner", "Machine maintenance/downtime."),
]

_NAV_ITEMS = [
    {"label": "Manufacturing Home", "type": "internal", "target": "/manufacturing"},
    {"label": "BOMs", "type": "internal", "target": "/manufacturing/boms"},
    {"label": "Production Orders", "type": "internal", "target": "/manufacturing/orders"},
    {"label": "MRP", "type": "internal", "target": "/manufacturing/mrp"},
    {"label": "Quality", "type": "internal", "target": "/manufacturing/quality"},
]


def build_manufacturing_manifest() -> dict:
    return {
        "schema_version": 1,
        "roles": MANUFACTURING_ROLES,
        "navigations": [{
            "ref": "main", "name": "Manufacturing Menu", "scope": "app",
            "tree": [{"label": "Manufacturing", "items": _NAV_ITEMS}],
        }],
        "home_layouts": [{"ref": "home", "name": "Manufacturing Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Manufacturing"}]}],
        "applications": [{
            "slug": "manufacturing", "name": "Manufacturing", "icon": "Factory",
            "color": "#9333ea", "included_entity_slugs": [], "navigation_ref": "main",
            "home_layout_ref": "home", "role_slugs": [r["slug"] for r in MANUFACTURING_ROLES],
            "is_published": True,
        }],
    }


def seed_manufacturing_template():
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="manufacturing",
        defaults={
            "name": "Manufacturing",
            "category": "Manufacturing",
            "description": "Enterprise manufacturing + MRP — multi-level BOMs, routings, work "
                           "centers, production orders, material reservation, MRP, costing, quality "
                           "(NCR/CAPA), OEE and full lot traceability. Native engines integrated "
                           "with Inventory, Procurement and Accounting.",
            "icon": "Factory", "color": "#9333ea", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_manufacturing_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
