"""
CRM Solution blueprint (Phase P2.6).

The ENTIRE CRM solution — Leads, Accounts, Contacts, Opportunities, Activities + their
relationships, forms, views, workflows, roles, dashboards, reports, notifications, application/
navigation/home — is expressed here as a curated extended manifest and installed through the
P2.4A Solution Template Framework. Native code (``services.py``) is a thin lifecycle layer over
the reusable ``SolutionDocumentService`` (numbering + audit); CRM ships almost 100% framework.
"""
from __future__ import annotations


def _f(slug, name, field_type, **kw):
    f = {"slug": slug, "name": name, "field_type": field_type, "is_promoted": True}
    f.update(kw)
    return f


def _lookup(slug, name, target):
    return _f(slug, name, "lookup", config={"target_entity_slug": target})


def _select(slug, name, *choices):
    return _f(slug, name, "select", config={"choices": list(choices)})


def _status(*choices):
    return _f("status", "Status", "status", config={"choices": list(choices)})


def _entity(slug, name, plural, fields):
    return {"slug": slug, "name": name, "plural_name": plural, "fields": fields}


# ── business objects ─────────────────────────────────────────────────────────
CRM_OBJECTS: dict[str, dict] = {
    "lead": _entity("lead", "Lead", "Leads", [
        _f("number", "Lead Number", "text", is_unique=True),
        _f("first_name", "First Name", "text"),
        _f("last_name", "Last Name", "text", is_required=True),
        _f("company", "Company", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _select("source", "Source", "web", "referral", "event", "cold_call", "other"),
        _f("owner", "Owner", "user"),
        _status("new", "contacted", "qualified", "disqualified"),
        _f("notes", "Notes", "textarea"),
    ]),
    "account": _entity("account", "Account", "Accounts", [
        _f("number", "Account Number", "text", is_unique=True),
        _f("name", "Name", "text", is_required=True),
        _f("industry", "Industry", "text"),
        _f("website", "Website", "url"),
        _f("revenue", "Revenue", "currency"),
        _status("prospect", "active", "inactive"),
        _f("owner", "Owner", "user"),
    ]),
    "contact": _entity("contact", "Contact", "Contacts", [
        _lookup("account", "Account", "account"),
        _f("name", "Name", "text", is_required=True),
        _f("title", "Title", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("mobile", "Mobile", "phone"),
    ]),
    "opportunity": _entity("opportunity", "Opportunity", "Opportunities", [
        _f("number", "Opportunity Number", "text", is_unique=True),
        _lookup("account", "Account", "account"),
        _lookup("contact", "Contact", "contact"),
        _f("value", "Value", "currency"),
        _f("expected_close_date", "Expected Close Date", "date"),
        _f("probability", "Probability", "percent"),
        _f("stage", "Stage", "status", config={
            "choices": ["prospecting", "qualification", "proposal", "negotiation",
                        "won", "lost"]}),
        _f("owner", "Owner", "user"),
        _f("close_reason", "Close Reason", "text"),
    ]),
    "activity": _entity("activity", "Activity", "Activities", [
        _select("type", "Type", "call", "meeting", "email", "task", "follow_up"),
        _f("subject", "Subject", "text", is_required=True),
        _f("due_date", "Due Date", "date"),
        _f("owner", "Owner", "user"),
        _f("related_type", "Related Type", "text"),
        _f("related_id", "Related Record", "text"),
        _status("open", "completed"),
    ]),
}

# Numbered documents → sequence prefix (P2.1 Numbering).
CRM_SEQUENCES = {
    "lead": {"name": "Lead", "prefix": "LEAD-", "padding": 6},
    "account": {"name": "Account", "prefix": "ACC-", "padding": 6},
    "opportunity": {"name": "Opportunity", "prefix": "OPP-", "padding": 6},
}
EVENT_KEY = {"lead": "lead", "account": "account", "opportunity": "opportunity",
             "contact": "contact", "activity": "activity"}
_MAIN = list(CRM_OBJECTS.keys())


# ── workflows ────────────────────────────────────────────────────────────────
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created"):
    return {"slug": slug, "name": name, "trigger_type": trigger_type, "trigger_config": {},
            "entity_slug": entity_slug, "steps": steps, "edges": edges}


def _assign_notify(notify):
    return ([{"slug": "assign", "step_type": "action_set_field", "name": "Assign",
              "is_entry": True, "config": {"field": "status", "value": "contacted"}},
             {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
              "config": {"template_slug": notify}}],
            [{"source": "assign", "target": "notify"}])


def _approval(notify):
    return ([{"slug": "start", "step_type": "condition", "name": "Start", "is_entry": True,
              "config": {}},
             {"slug": "review", "step_type": "approval", "name": "Manager Review", "config": {}},
             {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
              "config": {"template_slug": notify}}],
            [{"source": "start", "target": "review"}, {"source": "review", "target": "notify"}])


CRM_WORKFLOWS = [
    _wf("lead_assignment", "Lead Assignment", "lead", *_assign_notify("lead_assigned")),
    _wf("lead_qualification", "Lead Qualification", "lead", *_assign_notify("lead_assigned"),
        trigger_type="record_updated"),
    _wf("opportunity_review", "Opportunity Review", "opportunity",
        *_approval("opportunity_escalated")),
    _wf("opportunity_closure", "Opportunity Closure", "opportunity",
        *_assign_notify("opportunity_won"), trigger_type="record_updated"),
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
CRM_ROLES = [
    _role("sales_manager", "Sales Manager", "Full CRM access.", [(None, _FULL + ["admin"])]),
    _role("sales_representative", "Sales Representative", "Own leads and opportunities.",
          [("lead", _FULL), ("opportunity", _FULL), ("contact", _FULL),
           ("activity", _FULL), ("account", ["read", "update"])]),
    _role("sales_administrator", "Sales Administrator", "Configuration and reporting.",
          [(None, ["read", "export"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


CRM_REPORTS = [
    _report("lead_funnel_report", "Lead Funnel", "lead", "funnel"),
    _report("pipeline_report", "Pipeline Report", "opportunity", "pivot"),
    _report("forecast_report", "Forecast Report", "opportunity"),
    _report("win_loss_report", "Win/Loss Analysis", "opportunity", "pivot"),
    _report("sales_performance_report", "Sales Performance Report", "opportunity"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


CRM_DASHBOARDS = [
    {"slug": "sales_executive_dashboard", "name": "Sales Executive Dashboard",
     "is_default": True, "widgets": [
         _w("metric_card", "Pipeline Value", 0, 0, 3, 2),
         _w("metric_card", "Forecast", 3, 0, 3, 2),
         _w("metric_card", "Win Rate", 6, 0, 3, 2),
         _w("report", "Pipeline", 0, 2, 12, 4, report_slug="pipeline_report"),
     ]},
    {"slug": "sales_operations_dashboard", "name": "Sales Operations Dashboard", "widgets": [
        _w("report", "Lead Funnel", 0, 0, 6, 4, report_slug="lead_funnel_report"),
        _w("report", "Win / Loss", 6, 0, 6, 4, report_slug="win_loss_report"),
        _w("activity_feed", "Activity", 0, 4, 6, 4),
    ]},
]

CRM_NOTIFICATIONS = [
    {"slug": "lead_assigned", "name": "Lead Assigned", "channels": ["in_app"],
     "subject_template": "Lead assigned to you", "body_template": "A new lead is yours."},
    {"slug": "opportunity_escalated", "name": "Opportunity Escalated", "channels": ["in_app"],
     "subject_template": "Opportunity needs review", "body_template": "Please review."},
    {"slug": "opportunity_won", "name": "Opportunity Won", "channels": ["in_app"],
     "subject_template": "Opportunity won", "body_template": "Congratulations!"},
    {"slug": "followup_overdue", "name": "Follow-up Overdue", "channels": ["in_app"],
     "subject_template": "Follow-up overdue", "body_template": "An activity is overdue."},
]


# ── forms / views / app ──────────────────────────────────────────────────────
def _form_for(slug):
    obj = CRM_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = CRM_OBJECTS[slug]
    field_slugs = {f["slug"] for f in obj["fields"]}
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    group_field = "stage" if "stage" in field_slugs else (
        "status" if "status" in field_slugs else None)
    if group_field:
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Pipeline",
                      "view_type": "kanban", "config": {"group_by": group_field}})
    return views


def build_crm_manifest() -> dict:
    return {
        "schema_version": 1,
        "entities": list(CRM_OBJECTS.values()),
        "forms": [_form_for(s) for s in CRM_OBJECTS],
        "views": [v for s in CRM_OBJECTS for v in _views_for(s)],
        "workflows": CRM_WORKFLOWS,
        "reports": CRM_REPORTS,
        "notification_templates": CRM_NOTIFICATIONS,
        "roles": CRM_ROLES,
        "dashboards": CRM_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "CRM Menu", "scope": "app",
            "tree": [{"label": "Sales", "items": [
                {"label": CRM_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                for s in _MAIN]}],
        }],
        "home_layouts": [{"ref": "home", "name": "CRM Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "CRM"}]}],
        "applications": [{
            "slug": "crm", "name": "CRM", "icon": "Users", "color": "#7c3aed",
            "included_entity_slugs": _MAIN, "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in CRM_ROLES], "is_published": True,
        }],
    }


def seed_crm_template():
    """Upsert the published, system CRM SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="crm",
        defaults={
            "name": "CRM",
            "category": "CRM",
            "description": "Complete sales CRM — Leads, Accounts, Contacts, Opportunities and "
                           "Activities with the Lead→Qualified→Opportunity→Won/Lost pipeline, "
                           "workflows, roles, dashboards and reports. Ready to use.",
            "icon": "Users", "color": "#7c3aed", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_crm_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
