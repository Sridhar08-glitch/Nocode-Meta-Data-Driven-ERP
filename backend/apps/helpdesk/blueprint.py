"""
Helpdesk / Customer Service / ITSM blueprint (Phase P2.11).

The configurable surface — tickets, categories, knowledge base, ticket tasks/comments, problems,
ITSM changes, major incidents, service contracts, CSAT, agent profiles, field-service visits — is
provisioned through the Solution Template Framework (metadata entities/forms/views/workflows/roles/
dashboards/reports/nav/app). Native code is a thin lifecycle + the assignment/escalation/knowledge/
CSAT engines (``services.py``); SLA reuses the P1.19 SLA engine. Cross-module reuse: ticket.customer
→ CRM customer, ticket.asset → Assets asset, ticket.project → Projects project (no duplicate masters).
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


HELPDESK_OBJECTS: dict[str, dict] = {
    "ticket_category": _e("ticket_category", "Ticket Category", "Ticket Categories", [
        _f("name", "Name", "text", is_required=True),
        _sel("category_type", "Type", "incident", "service_request", "change", "problem",
             "question", "access_request", "hardware", "software"),
        _f("description", "Description", "textarea"),
        _f("default_team", "Default Team", "text")]),
    "ticket": _e("ticket", "Ticket", "Tickets", [
        _f("number", "Ticket Number", "text", is_unique=True),
        _f("title", "Title", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _lk("category", "Category", "ticket_category"),
        _f("subcategory", "Subcategory", "text"),
        _sel("priority", "Priority", "low", "medium", "high", "urgent"),
        _sel("severity", "Severity", "s1", "s2", "s3", "s4"),
        _sel("source", "Source", "portal", "email", "api", "manual", "chat", "mobile"),
        _lk("customer", "Customer", "customer"),
        _lk("contact", "Contact", "contact"),
        _lk("asset", "Asset", "asset"),
        _lk("project", "Project", "project"),
        _f("assigned_team", "Assigned Team", "text"),
        _f("assigned_agent", "Assigned Agent", "user"),
        _f("escalation_level", "Escalation Level", "integer"),
        _f("opened_date", "Opened Date", "datetime"),
        _f("closed_date", "Closed Date", "datetime"),
        _st("new", "open", "assigned", "in_progress", "waiting_customer", "waiting_vendor",
            "resolved", "closed", "cancelled")]),
    "ticket_task": _e("ticket_task", "Ticket Task", "Ticket Tasks", [
        _lk("ticket", "Ticket", "ticket"), _f("title", "Title", "text", is_required=True),
        _f("assignee", "Assignee", "user"), _f("due_date", "Due Date", "date"),
        _st("open", "completed")]),
    "ticket_comment": _e("ticket_comment", "Ticket Comment", "Ticket Comments", [
        _lk("ticket", "Ticket", "ticket"), _f("body", "Comment", "textarea", is_required=True),
        _f("is_internal", "Internal Note", "boolean"), _f("author", "Author", "user")]),
    "kb_article": _e("kb_article", "Knowledge Article", "Knowledge Articles", [
        _f("title", "Title", "text", is_required=True),
        _f("content", "Content", "textarea"), _f("category", "Category", "text"),
        _f("tags", "Tags", "text"), _f("author", "Author", "user"),
        _f("views_count", "Views", "integer"), _st("draft", "published", "archived")]),
    "problem": _e("problem", "Problem", "Problems", [
        _f("title", "Title", "text", is_required=True),
        _f("root_cause", "Root Cause", "textarea"),
        _sel("impact", "Impact", "low", "medium", "high"),
        _f("resolution", "Resolution", "textarea"),
        _f("related_tickets", "Related Tickets", "text"),
        _st("open", "investigating", "resolved", "closed")]),
    "itsm_change": _e("itsm_change", "Change Request", "Change Requests", [
        _f("title", "Title", "text", is_required=True),
        _sel("risk", "Risk", "low", "medium", "high"),
        _sel("impact", "Impact", "low", "medium", "high"),
        _f("rollback_plan", "Rollback Plan", "textarea"),
        _st("draft", "pending", "approved", "rejected", "implemented")]),
    "major_incident": _e("major_incident", "Major Incident", "Major Incidents", [
        _f("title", "Title", "text", is_required=True),
        _f("declared_by", "Declared By", "user"),
        _f("stakeholders", "Stakeholders", "textarea"),
        _f("timeline", "Incident Timeline", "textarea"),
        _st("declared", "mitigating", "resolved")]),
    "service_contract": _e("service_contract", "Service Contract", "Service Contracts", [
        _lk("customer", "Customer", "customer"), _f("name", "Name", "text", is_required=True),
        _f("coverage", "Coverage", "textarea"),
        _sel("sla_level", "SLA Level", "bronze", "silver", "gold", "platinum"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date"),
        _st("active", "expired")]),
    "ticket_csat": _e("ticket_csat", "CSAT", "CSAT Responses", [
        _lk("ticket", "Ticket", "ticket"), _f("rating", "Rating", "rating"),
        _f("feedback", "Feedback", "textarea"), _f("comments", "Comments", "textarea")]),
    "agent_profile": _e("agent_profile", "Agent Profile", "Agent Profiles", [
        _f("agent", "Agent", "user"), _f("team", "Team", "text"),
        _f("skills", "Skills", "text"), _f("is_available", "Available", "boolean"),
        _f("open_ticket_count", "Open Tickets", "integer")]),
    "field_service_visit": _e("field_service_visit", "Field Service Visit",
                              "Field Service Visits", [
        _lk("ticket", "Ticket", "ticket"), _f("technician", "Technician", "user"),
        _f("site", "Site", "text"), _f("visit_date", "Visit Date", "datetime"),
        _f("travel_time_hours", "Travel Time (hours)", "decimal"),
        _f("service_report", "Service Report", "textarea"),
        _st("scheduled", "completed", "cancelled")]),
}

HELPDESK_SEQUENCES = {"ticket": {"name": "Ticket", "prefix": "TKT-", "padding": 6}}
_MAIN = list(HELPDESK_OBJECTS.keys())


# ── workflows ────────────────────────────────────────────────────────────────
def _wf(slug, name, entity_slug, notify="ticket_assigned", trigger_type="record_created"):
    return {"slug": slug, "name": name, "trigger_type": trigger_type, "trigger_config": {},
            "entity_slug": entity_slug,
            "steps": [
                {"slug": "start", "step_type": "condition", "name": "Start", "is_entry": True,
                 "config": {}},
                {"slug": "review", "step_type": "approval", "name": "Review", "config": {}},
                {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
                 "config": {"template_slug": notify}}],
            "edges": [{"source": "start", "target": "review"},
                      {"source": "review", "target": "notify"}]}


HELPDESK_WORKFLOWS = [
    _wf("incident_workflow", "Incident Workflow", "ticket", "ticket_created"),
    _wf("service_request_workflow", "Service Request Workflow", "ticket", "ticket_assigned"),
    _wf("problem_workflow", "Problem Workflow", "problem", "ticket_escalated"),
    _wf("change_workflow", "Change Workflow", "itsm_change", "ticket_escalated"),
    _wf("major_incident_workflow", "Major Incident Workflow", "major_incident", "sla_breach"),
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
HELPDESK_ROLES = [
    _role("helpdesk_administrator", "Helpdesk Administrator", "Full access.",
          [(None, _FULL + ["admin"])]),
    _role("service_desk_manager", "Service Desk Manager", "Service desk ops.", [(None, _FULL)]),
    _role("helpdesk_team_lead", "Team Lead", "Lead a support team.",
          [("ticket", _FULL), ("problem", _FULL), ("kb_article", _FULL)]),
    _role("support_agent", "Support Agent", "Work tickets.",
          [("ticket", ["create", "read", "update"]), ("ticket_task", _FULL),
           ("ticket_comment", _FULL), ("kb_article", ["read"])]),
    _role("helpdesk_technician", "Technician", "Field service.",
          [("field_service_visit", _FULL), ("ticket", ["read", "update"])]),
    _role("helpdesk_customer", "Customer", "Portal access.",
          [("ticket", ["create", "read"]), ("ticket_comment", ["create", "read"]),
           ("kb_article", ["read"]), ("ticket_csat", ["create"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


HELPDESK_REPORTS = [
    _report("ticket_summary", "Ticket Summary", "ticket", "pivot"),
    _report("sla_compliance_report", "SLA Compliance", "ticket", "pivot"),
    _report("resolution_time_report", "Resolution Time", "ticket", "pivot"),
    _report("escalation_report", "Escalation Report", "ticket", "pivot"),
    _report("agent_performance_report", "Agent Performance", "ticket", "pivot"),
    _report("csat_report", "CSAT Report", "ticket_csat", "pivot"),
    _report("knowledge_usage_report", "Knowledge Usage", "kb_article"),
    _report("asset_support_history", "Asset Support History", "ticket"),
    _report("problem_analysis_report", "Problem Analysis", "problem"),
    _report("change_analysis_report", "Change Analysis", "itsm_change"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


HELPDESK_DASHBOARDS = [
    {"slug": "helpdesk_executive_dashboard", "name": "Executive Dashboard", "is_default": True,
     "widgets": [
         _w("metric_card", "Open Tickets", 0, 0, 3, 2),
         _w("metric_card", "SLA Compliance", 3, 0, 3, 2),
         _w("metric_card", "CSAT", 6, 0, 3, 2),
         _w("report", "Ticket Summary", 0, 2, 6, 4, report_slug="ticket_summary"),
         _w("report", "Resolution Trends", 6, 2, 6, 4, report_slug="resolution_time_report"),
     ]},
    {"slug": "helpdesk_service_desk_dashboard", "name": "Service Desk Dashboard", "widgets": [
        _w("report", "Escalations", 0, 0, 6, 4, report_slug="escalation_report"),
        _w("report", "SLA Compliance", 6, 0, 6, 4, report_slug="sla_compliance_report"),
    ]},
    {"slug": "helpdesk_agent_dashboard", "name": "Agent Dashboard", "widgets": [
        _w("report", "My Queue", 0, 0, 6, 4, report_slug="ticket_summary"),
        _w("report", "Agent Performance", 6, 0, 6, 4, report_slug="agent_performance_report"),
    ]},
]

HELPDESK_NOTIFICATIONS = [
    {"slug": s, "name": n, "channels": ["in_app"], "subject_template": n, "body_template": n + "."}
    for s, n in [
        ("ticket_created", "Ticket Created"), ("ticket_assigned", "Ticket Assigned"),
        ("ticket_escalated", "Ticket Escalated"), ("sla_breach", "SLA Breach"),
        ("comment_added", "Comment Added"), ("ticket_resolved", "Ticket Resolved"),
        ("csat_requested", "CSAT Requested"),
    ]
]


# ── forms / views / app ──────────────────────────────────────────────────────
def _form_for(slug):
    obj = HELPDESK_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = HELPDESK_OBJECTS[slug]
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if any(f["slug"] == "status" for f in obj["fields"]):
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


_NAV = [
    ("Service Desk", ["ticket", "ticket_category", "ticket_task"]),
    ("ITSM", ["problem", "itsm_change", "major_incident"]),
    ("Knowledge", ["kb_article"]),
    ("Customers", ["service_contract", "ticket_csat"]),
    ("Field & Agents", ["field_service_visit", "agent_profile"]),
]


def build_helpdesk_manifest() -> dict:
    return {
        "schema_version": 1,
        "entities": list(HELPDESK_OBJECTS.values()),
        "forms": [_form_for(s) for s in HELPDESK_OBJECTS],
        "views": [v for s in HELPDESK_OBJECTS for v in _views_for(s)],
        "workflows": HELPDESK_WORKFLOWS,
        "reports": HELPDESK_REPORTS,
        "notification_templates": HELPDESK_NOTIFICATIONS,
        "roles": HELPDESK_ROLES,
        "dashboards": HELPDESK_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "Helpdesk Menu", "scope": "app",
            "tree": [{"label": label, "items": [
                {"label": HELPDESK_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                for s in items]} for label, items in _NAV],
        }],
        "home_layouts": [{"ref": "home", "name": "Helpdesk Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Helpdesk & ITSM"}]}],
        "applications": [{
            "slug": "helpdesk", "name": "Helpdesk & ITSM", "icon": "LifeBuoy",
            "color": "#0891b2", "included_entity_slugs": _MAIN, "navigation_ref": "main",
            "home_layout_ref": "home", "role_slugs": [r["slug"] for r in HELPDESK_ROLES],
            "is_published": True,
        }],
    }


def seed_helpdesk_template():
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="helpdesk",
        defaults={
            "name": "Helpdesk & ITSM",
            "category": "Helpdesk",
            "description": "Enterprise helpdesk, customer service and ITSM — tickets with SLAs, "
                           "assignment + escalation engines, knowledge base, problem/change/major-"
                           "incident management, CSAT, field service and a customer portal. Reuses "
                           "the SLA engine; integrates CRM/Assets/Projects.",
            "icon": "LifeBuoy", "color": "#0891b2", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_helpdesk_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
