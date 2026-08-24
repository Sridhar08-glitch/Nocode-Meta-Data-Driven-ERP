"""
Enterprise Asset Management (EAM) blueprint (Phase P2.9).

The configurable surface — asset registry, categories/types, assignments, transfers, maintenance
plans + work orders, inspections, requests, warranties, contracts, reservations, inventory counts
— is provisioned through the Solution Template Framework (metadata entities/forms/views/workflows/
roles/dashboards/reports/nav/app). Only the integrity-critical engines are native (depreciation,
disposal, retirement GL — see ``services.py``). Vendor references reuse the Procurement ``vendor``
entity by lookup (no duplicate vendor master).
"""
from __future__ import annotations


def _f(slug, name, field_type, **kw):
    f = {"slug": slug, "name": name, "field_type": field_type, "is_promoted": True}
    f.update(kw)
    return f


def _lk(slug, name, target):
    return _f(slug, name, "lookup", config={"target_entity_slug": target})


def _sel(slug, name, *choices):
    return _f(slug, name, "select", config={"choices": list(choices)})


def _st(*choices):
    return _f("status", "Status", "status", config={"choices": list(choices)})


def _e(slug, name, plural, fields):
    return {"slug": slug, "name": name, "plural_name": plural, "fields": fields}


ASSET_OBJECTS: dict[str, dict] = {
    "asset_category": _e("asset_category", "Asset Category", "Asset Categories", [
        _f("name", "Name", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _sel("default_depreciation_method", "Default Depreciation Method",
             "straight_line", "declining_balance", "double_declining"),
        _f("default_useful_life_months", "Default Useful Life (months)", "integer")]),
    "asset_type": _e("asset_type", "Asset Type", "Asset Types", [
        _f("name", "Name", "text", is_required=True),
        _f("description", "Description", "textarea")]),
    "asset": _e("asset", "Asset", "Assets", [
        _f("number", "Asset Number", "text", is_unique=True),
        _f("name", "Asset Name", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _lk("asset_type", "Asset Type", "asset_type"),
        _lk("category", "Category", "asset_category"),
        _f("subcategory", "Subcategory", "text"),
        _f("serial_number", "Serial Number", "text"),
        _f("barcode", "Barcode", "barcode"),
        _f("qr_code", "QR Code", "text"),
        _f("manufacturer", "Manufacturer", "text"),
        _f("model", "Model", "text"),
        _f("purchase_date", "Purchase Date", "date"),
        _f("purchase_cost", "Purchase Cost", "currency"),
        _f("salvage_value", "Salvage Value", "currency"),
        _f("useful_life_months", "Useful Life (months)", "integer"),
        _f("current_value", "Current Value", "currency"),
        _f("accumulated_depreciation", "Accumulated Depreciation", "currency"),
        _f("net_book_value", "Net Book Value", "currency"),
        _st("draft", "in_service", "assigned", "under_maintenance", "retired", "disposed", "lost"),
        _lk("vendor", "Supplier", "vendor"),
        _f("branch", "Branch", "text"),
        _f("department", "Department", "text"),
        _f("cost_center", "Cost Center", "text")]),
    "asset_assignment": _e("asset_assignment", "Asset Assignment", "Asset Assignments", [
        _lk("asset", "Asset", "asset"),
        _f("employee", "Employee", "user"),
        _f("department", "Department", "text"),
        _f("team", "Team", "text"),
        _f("assigned_date", "Assigned Date", "date"),
        _f("return_date", "Return Date", "date"),
        _st("active", "returned")]),
    "asset_transfer": _e("asset_transfer", "Asset Transfer", "Asset Transfers", [
        _lk("asset", "Asset", "asset"),
        _sel("transfer_type", "Transfer Type", "employee", "department", "branch", "location"),
        _f("from_ref", "From", "text"), _f("to_ref", "To", "text"),
        _f("effective_date", "Effective Date", "date"), _st("draft", "approved")]),
    "maintenance_plan": _e("maintenance_plan", "Maintenance Plan", "Maintenance Plans", [
        _lk("asset", "Asset", "asset"),
        _f("maintenance_type", "Maintenance Type", "text"),
        _sel("frequency", "Frequency", "daily", "weekly", "monthly", "quarterly", "annual"),
        _f("next_due_date", "Next Due Date", "date"), _f("is_active", "Active", "boolean")]),
    "maintenance_work_order": _e(
        "maintenance_work_order", "Work Order", "Work Orders", [
            _lk("asset", "Asset", "asset"),
            _f("issue", "Issue", "textarea"),
            _f("technician", "Technician", "user"),
            _f("cost", "Cost", "currency"),
            _st("open", "in_progress", "completed", "cancelled")]),
    "inspection": _e("inspection", "Inspection", "Inspections", [
        _lk("asset", "Asset", "asset"),
        _f("date", "Date", "date"), _f("inspector", "Inspector", "user"),
        _sel("result", "Result", "passed", "failed", "requires_attention"),
        _f("notes", "Notes", "textarea")]),
    "asset_request": _e("asset_request", "Asset Request", "Asset Requests", [
        _f("employee", "Employee", "user"),
        _f("requested_asset", "Requested Asset", "text"),
        _f("justification", "Justification", "textarea"),
        _st("draft", "pending", "approved", "rejected", "fulfilled")]),
    "warranty": _e("warranty", "Warranty", "Warranties", [
        _lk("asset", "Asset", "asset"),
        _f("warranty_start", "Warranty Start", "date"),
        _f("warranty_end", "Warranty End", "date"),
        _lk("vendor", "Provider", "vendor"),
        _f("coverage_details", "Coverage Details", "textarea")]),
    "asset_contract": _e("asset_contract", "Asset Contract", "Asset Contracts", [
        _lk("asset", "Asset", "asset"),
        _sel("contract_type", "Contract Type", "lease", "rental", "service"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date"),
        _f("cost", "Cost", "currency"), _lk("vendor", "Vendor", "vendor")]),
    "asset_reservation": _e("asset_reservation", "Asset Reservation", "Asset Reservations", [
        _lk("asset", "Asset", "asset"),
        _f("reserved_by", "Reserved By", "user"),
        _f("start_date", "Start", "datetime"), _f("end_date", "End", "datetime"),
        _st("reserved", "released")]),
    "asset_inventory_count": _e(
        "asset_inventory_count", "Inventory Count", "Inventory Counts", [
            _lk("asset", "Asset", "asset"),
            _f("count_date", "Count Date", "date"),
            _sel("method", "Method", "manual", "barcode", "qr"),
            _sel("result", "Result", "found", "missing", "discrepancy"),
            _f("notes", "Notes", "textarea")]),
}

ASSET_SEQUENCES = {"asset": {"name": "Asset", "prefix": "AST-", "padding": 6}}
EVENT_KEY = {"asset": "asset"}
_MAIN = list(ASSET_OBJECTS.keys())


# ── workflows ────────────────────────────────────────────────────────────────
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created"):
    return {"slug": slug, "name": name, "trigger_type": trigger_type, "trigger_config": {},
            "entity_slug": entity_slug, "steps": steps, "edges": edges}


def _approval(notify):
    return ([{"slug": "start", "step_type": "condition", "name": "Start", "is_entry": True,
              "config": {}},
             {"slug": "review", "step_type": "approval", "name": "Review", "config": {}},
             {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
              "config": {"template_slug": notify}}],
            [{"source": "start", "target": "review"}, {"source": "review", "target": "notify"}])


ASSET_WORKFLOWS = [
    _wf("asset_request_approval", "Asset Request Approval", "asset_request",
        *_approval("assignment_created")),
    _wf("assignment_approval", "Asset Assignment Approval", "asset_assignment",
        *_approval("assignment_created")),
    _wf("maintenance_approval", "Maintenance Approval", "maintenance_work_order",
        *_approval("maintenance_due")),
    _wf("transfer_approval", "Transfer Approval", "asset_transfer", *_approval("maintenance_due")),
]


# ── roles ────────────────────────────────────────────────────────────────────
def _role(slug, name, description, grants):
    perms = []
    for entity_slug, actions in grants:
        for action in actions:
            p = {"resource_type": "entity", "action": action}
            if entity_slug:
                p["entity_slug"] = entity_slug
            perms.append(p)
    return {"slug": slug, "name": name, "description": description, "permissions": perms}


_FULL = ["create", "read", "update", "delete", "export"]
ASSET_ROLES = [
    _role("asset_administrator", "Asset Administrator", "Full asset access.",
          [(None, _FULL + ["admin"])]),
    _role("asset_manager", "Asset Manager", "Asset operations.", [(None, _FULL)]),
    _role("asset_technician", "Technician", "Maintenance and inspections.",
          [("maintenance_work_order", _FULL), ("inspection", _FULL),
           ("maintenance_plan", ["read", "update"]), ("asset", ["read"])]),
    _role("asset_department_manager", "Department Manager", "Approvals.",
          [("asset_request", ["read", "update"]), ("asset_assignment", ["read", "update"]),
           ("asset_transfer", ["read", "update"]), ("asset", ["read"])]),
    _role("asset_employee", "Employee", "Request and view assigned assets.",
          [("asset", ["read"]), ("asset_request", ["create", "read"]),
           ("asset_assignment", ["read"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


ASSET_REPORTS = [
    _report("asset_register", "Asset Register", "asset"),
    _report("asset_assignment_report", "Asset Assignment Report", "asset_assignment"),
    _report("asset_transfer_report", "Asset Transfer Report", "asset_transfer"),
    _report("asset_valuation_report", "Asset Valuation Report", "asset", "pivot"),
    _report("depreciation_report", "Depreciation Report", "asset", "pivot"),
    _report("maintenance_report", "Maintenance Report", "maintenance_work_order"),
    _report("warranty_report", "Warranty Report", "warranty"),
    _report("disposal_report", "Disposal Report", "asset"),
    _report("retirement_report", "Retirement Report", "asset"),
    _report("inspection_report", "Inspection Report", "inspection"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


ASSET_DASHBOARDS = [
    {"slug": "asset_executive_dashboard", "name": "Asset Executive Dashboard", "is_default": True,
     "widgets": [
         _w("metric_card", "Total Assets", 0, 0, 3, 2),
         _w("metric_card", "Asset Value", 3, 0, 3, 2),
         _w("report", "Assets by Category", 0, 2, 6, 4, report_slug="asset_register"),
         _w("report", "Depreciation Summary", 6, 2, 6, 4, report_slug="depreciation_report"),
     ]},
    {"slug": "asset_maintenance_dashboard", "name": "Maintenance Dashboard", "widgets": [
        _w("report", "Open Work Orders", 0, 0, 6, 4, report_slug="maintenance_report"),
        _w("report", "Warranty Expiry", 6, 0, 6, 4, report_slug="warranty_report"),
        _w("report", "Inspections", 0, 4, 6, 4, report_slug="inspection_report"),
    ]},
]

ASSET_NOTIFICATIONS = [
    {"slug": s, "name": n, "channels": ["in_app"], "subject_template": n, "body_template": n + "."}
    for s, n in [
        ("assignment_created", "Assignment Created"), ("return_due", "Return Due"),
        ("warranty_expiring", "Warranty Expiring"), ("maintenance_due", "Maintenance Due"),
        ("inspection_due", "Inspection Due"), ("disposal_approved", "Disposal Approved"),
        ("retirement_completed", "Retirement Completed"),
    ]
]


# ── forms / views / app ──────────────────────────────────────────────────────
def _form_for(slug):
    obj = ASSET_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = ASSET_OBJECTS[slug]
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if any(f["slug"] == "status" for f in obj["fields"]):
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


_NAV = [
    ("Registry", ["asset", "asset_category", "asset_type"]),
    ("Operations", ["asset_assignment", "asset_transfer", "asset_request", "asset_reservation"]),
    ("Maintenance", ["maintenance_plan", "maintenance_work_order", "inspection"]),
    ("Records", ["warranty", "asset_contract", "asset_inventory_count"]),
]


def build_assets_manifest() -> dict:
    return {
        "schema_version": 1,
        "entities": list(ASSET_OBJECTS.values()),
        "forms": [_form_for(s) for s in ASSET_OBJECTS],
        "views": [v for s in ASSET_OBJECTS for v in _views_for(s)],
        "workflows": ASSET_WORKFLOWS,
        "reports": ASSET_REPORTS,
        "notification_templates": ASSET_NOTIFICATIONS,
        "roles": ASSET_ROLES,
        "dashboards": ASSET_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "Assets Menu", "scope": "app",
            "tree": [{"label": label, "items": [
                {"label": ASSET_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                for s in items]} for label, items in _NAV],
        }],
        "home_layouts": [{"ref": "home", "name": "Assets Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Asset Management"}]}],
        "applications": [{
            "slug": "assets", "name": "Asset Management", "icon": "Package", "color": "#b45309",
            "included_entity_slugs": _MAIN, "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in ASSET_ROLES], "is_published": True,
        }],
    }


def seed_assets_template():
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="assets",
        defaults={
            "name": "Asset Management",
            "category": "Assets",
            "description": "Enterprise asset management — registry, categories, assignments, "
                           "transfers, maintenance, inspections, warranties and contracts with a "
                           "native depreciation + disposal engine and GL integration.",
            "icon": "Package", "color": "#b45309", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_assets_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
