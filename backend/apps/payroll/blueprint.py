"""
Payroll Solution blueprint (Phase P2.8).

Payroll is a NATIVE engine (not metadata), so — unlike CRM/HR — its data/dashboards/reports/
workflows are native, not provisioned by the framework. The SolutionTemplate still provisions
the configurable surface that IS framework-expressible: the payroll Roles and the Application +
Navigation + Home that surface the native ``/payroll`` UI (navigation uses ``internal`` links to
the native routes). Installable from the Solution Catalog and the Create Solution Wizard.
"""
from __future__ import annotations


def _role(slug, name, description):
    # Named org roles; the native payroll API enforces admin/SoD itself (payroll has no
    # metadata entities to grant entity-permissions over).
    return {"slug": slug, "name": name, "description": description, "permissions": []}


PAYROLL_ROLES = [
    _role("payroll_administrator", "Payroll Administrator", "Full payroll configuration and runs."),
    _role("payroll_manager", "Payroll Manager", "Run, review and approve payroll."),
    _role("payroll_hr_manager", "HR Manager", "People data feeding payroll."),
    _role("payroll_finance_manager", "Finance Manager", "Approve/post payroll to the ledger."),
    _role("payroll_employee", "Employee", "Self-service payslip access."),
]

_NAV_ITEMS = [
    {"label": "Payroll Home", "type": "internal", "target": "/payroll"},
    {"label": "Salary Structures", "type": "internal", "target": "/payroll/structures"},
    {"label": "Pay Runs", "type": "internal", "target": "/payroll/runs"},
    {"label": "Payslips", "type": "internal", "target": "/payroll/payslips"},
    {"label": "Loans & Advances", "type": "internal", "target": "/payroll/loans"},
]


def build_payroll_manifest() -> dict:
    return {
        "schema_version": 1,
        "roles": PAYROLL_ROLES,
        "navigations": [{
            "ref": "main", "name": "Payroll Menu", "scope": "app",
            "tree": [{"label": "Payroll", "items": _NAV_ITEMS}],
        }],
        "home_layouts": [{"ref": "home", "name": "Payroll Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Payroll"}]}],
        "applications": [{
            "slug": "payroll", "name": "Payroll", "icon": "Banknote", "color": "#15803d",
            "included_entity_slugs": [], "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in PAYROLL_ROLES], "is_published": True,
        }],
    }


def seed_payroll_template():
    """Upsert the published, system Payroll SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="payroll",
        defaults={
            "name": "Payroll",
            "category": "Payroll",
            "description": "Enterprise payroll engine — salary structures, pay components, a safe "
                           "formula engine, payroll periods/runs, payslips with GL posting, loans, "
                           "advances, overtime, retro and final settlement. Native calculation "
                           "with segregation of duties and immutable posted payslips.",
            "icon": "Banknote", "color": "#15803d", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_payroll_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
