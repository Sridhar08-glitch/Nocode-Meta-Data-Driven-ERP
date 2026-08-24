"""
Procurement Solution blueprint (Phase P2.5).

The ENTIRE procurement solution — business objects, relationships, forms, views, workflows,
roles, dashboards, reports, application/navigation/home — is expressed here as a curated
extended manifest and installed through the P2.4A Solution Template Framework (no hand-built
forms/views/dashboards/roles). Native code (``services.py``) exists ONLY for the integrity
seams: gapless numbering, Goods-Receipt → Inventory ledger, Vendor-Bill → GL event, audit.

``seed_procurement_template`` upserts a published, system ``SolutionTemplate`` so Procurement
is installable from both the Solution Catalog and the Create Solution Wizard.
"""
from __future__ import annotations


# ── field + entity helpers ───────────────────────────────────────────────────
def _f(slug, name, field_type, **kw):
    f = {"slug": slug, "name": name, "field_type": field_type, "is_promoted": True}
    f.update(kw)
    return f


def _lookup(slug, name, target):
    return _f(slug, name, "lookup", config={"target_entity_slug": target})


def _status(*choices):
    return _f("status", "Status", "status", config={"choices": list(choices)})


def _entity(slug, name, plural, fields):
    return {"slug": slug, "name": name, "plural_name": plural, "fields": fields}


# ── business objects (provisioned via the framework) ─────────────────────────
PROCUREMENT_OBJECTS: dict[str, dict] = {
    "vendor": _entity("vendor", "Vendor", "Vendors", [
        _f("vendor_code", "Vendor Code", "text", is_unique=True),
        _f("name", "Vendor Name", "text", is_required=True),
        _status("active", "inactive", "blocked"),
        _f("tax_id", "Tax ID", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("address", "Address", "textarea"),
        _f("rating", "Rating", "rating"),
    ]),
    "vendor_contact": _entity("vendor_contact", "Vendor Contact", "Vendor Contacts", [
        _lookup("vendor", "Vendor", "vendor"),
        _f("name", "Name", "text", is_required=True),
        _f("role", "Role", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
    ]),
    "rfq": _entity("rfq", "RFQ", "RFQs", [
        _f("number", "RFQ Number", "text", is_unique=True),
        _lookup("vendor", "Vendor", "vendor"),
        _f("requested_date", "Requested Date", "date"),
        _status("draft", "sent", "quoted", "closed", "cancelled"),
        _f("notes", "Notes", "textarea"),
    ]),
    "rfq_line": _entity("rfq_line", "RFQ Line", "RFQ Lines", [
        _lookup("rfq", "RFQ", "rfq"),
        _f("item", "Item", "text"),
        _f("description", "Description", "text"),
        _f("quantity", "Quantity", "decimal"),
        _f("uom", "UOM", "text"),
        _f("expected_price", "Expected Price", "currency"),
    ]),
    "purchase_order": _entity("purchase_order", "Purchase Order", "Purchase Orders", [
        _f("number", "PO Number", "text", is_unique=True),
        _lookup("vendor", "Vendor", "vendor"),
        _f("order_date", "Order Date", "date"),
        _f("expected_delivery", "Expected Delivery", "date"),
        _f("amount", "Amount", "currency"),
        _status("draft", "pending_approval", "approved", "received", "closed", "cancelled"),
    ]),
    "purchase_order_line": _entity(
        "purchase_order_line", "Purchase Order Line", "Purchase Order Lines", [
            _lookup("purchase_order", "Purchase Order", "purchase_order"),
            _f("item", "Item", "text"),
            _f("quantity", "Quantity", "decimal"),
            _f("uom", "UOM", "text"),
            _f("unit_cost", "Unit Cost", "currency"),
            _f("total", "Total", "currency"),
        ]),
    "goods_receipt": _entity("goods_receipt", "Goods Receipt", "Goods Receipts", [
        _f("number", "Receipt Number", "text", is_unique=True),
        _lookup("purchase_order", "Purchase Order", "purchase_order"),
        _f("warehouse_code", "Warehouse Code", "text"),
        _f("receipt_date", "Receipt Date", "date"),
        _status("draft", "received", "posted", "cancelled"),
    ]),
    "goods_receipt_line": _entity(
        "goods_receipt_line", "Goods Receipt Line", "Goods Receipt Lines", [
            _lookup("goods_receipt", "Goods Receipt", "goods_receipt"),
            _f("item_sku", "Item SKU", "text"),
            _f("description", "Description", "text"),
            _f("quantity", "Quantity", "decimal"),
            _f("uom", "UOM", "text"),
            _f("unit_cost", "Unit Cost", "currency"),
        ]),
    "vendor_bill": _entity("vendor_bill", "Vendor Bill", "Vendor Bills", [
        _f("number", "Bill Number", "text", is_unique=True),
        _lookup("vendor", "Vendor", "vendor"),
        _lookup("purchase_order", "Purchase Order", "purchase_order"),
        _f("bill_date", "Bill Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("amount", "Amount", "currency"),
        _status("draft", "approved", "posted", "paid", "cancelled"),
    ]),
    "vendor_bill_line": _entity("vendor_bill_line", "Vendor Bill Line", "Vendor Bill Lines", [
        _lookup("vendor_bill", "Vendor Bill", "vendor_bill"),
        _f("item", "Item", "text"),
        _f("quantity", "Quantity", "decimal"),
        _f("unit_cost", "Unit Cost", "currency"),
        _f("total", "Total", "currency"),
    ]),
}

# Document types that carry a gapless number + their sequence prefix (P2.1 Numbering).
DOC_SEQUENCES = {
    "rfq": "RFQ",
    "purchase_order": "PO",
    "goods_receipt": "GR",
    "vendor_bill": "VB",
}

_MAIN_ENTITIES = list(PROCUREMENT_OBJECTS.keys())


# ── workflows (Workflow Library shape, bound to procurement entities) ────────
def _approval_wf(slug, name, entity_slug, notify="procurement_approval"):
    return {
        "slug": slug, "name": name, "trigger_type": "record_created",
        "trigger_config": {}, "entity_slug": entity_slug,
        "steps": [
            {"slug": "start", "step_type": "condition", "name": "Start", "is_entry": True,
             "config": {}},
            {"slug": "review", "step_type": "approval", "name": "Review", "config": {}},
            {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
             "config": {"template_slug": notify}},
        ],
        "edges": [{"source": "start", "target": "review"},
                  {"source": "review", "target": "notify"}],
    }


PROCUREMENT_WORKFLOWS = [
    _approval_wf("rfq_approval", "RFQ Approval", "rfq"),
    _approval_wf("po_approval", "Purchase Order Approval", "purchase_order"),
    _approval_wf("gr_validation", "Goods Receipt Validation", "goods_receipt"),
    _approval_wf("vb_approval", "Vendor Bill Approval", "vendor_bill"),
]


# ── roles (Role Library) ─────────────────────────────────────────────────────
def _role(slug, name, description, grants):
    """grants = list of (entity_slug, [actions]); entity_slug None = all procurement entities."""
    perms = []
    for entity_slug, actions in grants:
        for action in actions:
            p = {"resource_type": "entity", "action": action}
            if entity_slug:
                p["entity_slug"] = entity_slug
            perms.append(p)
    return {"slug": slug, "name": name, "description": description, "permissions": perms}


_FULL = ["create", "read", "update", "delete", "export"]
PROCUREMENT_ROLES = [
    _role("procurement_manager", "Procurement Manager", "Full procurement access.",
          [(None, _FULL + ["admin"])]),
    _role("buyer", "Buyer", "Manage RFQs and purchase orders.",
          [("rfq", _FULL), ("rfq_line", _FULL),
           ("purchase_order", _FULL), ("purchase_order_line", _FULL),
           ("vendor", ["read"]), ("vendor_contact", ["read"])]),
    _role("receiver", "Receiver", "Record and post goods receipts.",
          [("goods_receipt", _FULL), ("goods_receipt_line", _FULL),
           ("purchase_order", ["read"])]),
    _role("procurement_approver", "Approver", "Approve procurement documents.",
          [("rfq", ["read", "update"]), ("purchase_order", ["read", "update"]),
           ("vendor_bill", ["read", "update"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


PROCUREMENT_REPORTS = [
    _report("vendor_spend_report", "Vendor Spend Report", "vendor_bill", "pivot"),
    _report("po_aging_report", "Purchase Order Aging", "purchase_order"),
    _report("open_po_report", "Open PO Report", "purchase_order"),
    _report("rfq_conversion_report", "RFQ Conversion Report", "rfq"),
    _report("vendor_performance_report", "Vendor Performance Report", "vendor"),
]


def _widget(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title,
          "grid_x": x, "grid_y": y, "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


PROCUREMENT_DASHBOARDS = [
    {"slug": "procurement_operations", "name": "Procurement Operations", "is_default": True,
     "widgets": [
         _widget("metric_card", "Open RFQs", 0, 0, 3, 2),
         _widget("metric_card", "Pending Approvals", 3, 0, 3, 2),
         _widget("report", "Open Purchase Orders", 0, 2, 6, 4, report_slug="open_po_report"),
         _widget("report", "PO Aging (Late Deliveries)", 6, 2, 6, 4,
                 report_slug="po_aging_report"),
     ]},
    {"slug": "procurement_analytics", "name": "Procurement Analytics",
     "widgets": [
         _widget("report", "Vendor Performance", 0, 0, 6, 4,
                 report_slug="vendor_performance_report"),
         _widget("report", "Spend By Vendor", 6, 0, 6, 4, report_slug="vendor_spend_report"),
         _widget("report", "RFQ Conversion Rate", 0, 4, 6, 4,
                 report_slug="rfq_conversion_report"),
     ]},
]

PROCUREMENT_NOTIFICATIONS = [
    {"slug": "procurement_approval", "name": "Procurement Approval",
     "channels": ["in_app"], "subject_template": "Procurement approval needed",
     "body_template": "A procurement document needs your approval."},
]


# ── full manifest + seed ─────────────────────────────────────────────────────
def _form_for(slug):
    obj = PROCUREMENT_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"],
            "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = PROCUREMENT_OBJECTS[slug]
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if any(f["slug"] == "status" for f in obj["fields"]):
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "By Status",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


# Entities surfaced in navigation / the application (headers, not line items).
_NAV_ENTITIES = ["vendor", "rfq", "purchase_order", "goods_receipt", "vendor_bill"]


def build_procurement_manifest() -> dict:
    entities = list(PROCUREMENT_OBJECTS.values())
    forms = [_form_for(s) for s in PROCUREMENT_OBJECTS]
    views = [v for s in PROCUREMENT_OBJECTS for v in _views_for(s)]
    nav_items = [{"label": PROCUREMENT_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                 for s in _NAV_ENTITIES]
    return {
        "schema_version": 1,
        "entities": entities,
        "forms": forms,
        "views": views,
        "workflows": PROCUREMENT_WORKFLOWS,
        "reports": PROCUREMENT_REPORTS,
        "notification_templates": PROCUREMENT_NOTIFICATIONS,
        "roles": PROCUREMENT_ROLES,
        "dashboards": PROCUREMENT_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "Procurement Menu", "scope": "app",
            "tree": [{"label": "Procurement", "items": nav_items}],
        }],
        "home_layouts": [{
            "ref": "home", "name": "Procurement Home", "scope": "app",
            "widgets": [{"type": "card", "title": "Procurement"}],
        }],
        "applications": [{
            "slug": "procurement", "name": "Procurement", "icon": "ShoppingCart",
            "color": "#0e7490",
            "included_entity_slugs": _MAIN_ENTITIES,
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in PROCUREMENT_ROLES], "is_published": True,
        }],
    }


def seed_procurement_template():
    """Upsert the published, system Procurement SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="procurement",
        defaults={
            "name": "Procurement",
            "category": "Procurement",
            "description": "Full procurement lifecycle — Vendors, RFQs, Purchase Orders, "
                           "Goods Receipts and Vendor Bills with approval workflows, roles, "
                           "dashboards and reports. Inventory and GL integration wired in.",
            "icon": "ShoppingCart", "color": "#0e7490", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_procurement_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
