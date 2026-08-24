"""
Project Management + PSA blueprint (Phase P2.10).

The configurable surface — portfolios, programs, projects, members, skills, tasks (unlimited
hierarchy + agile types), milestones, deliverables, dependencies, sprints, timesheets, expenses,
risks, issues, change requests, quality reviews — is provisioned through the Solution Template
Framework (metadata entities/forms/views/workflows/roles/dashboards/reports/nav/app). Only the
computational engines are native (scheduling/critical-path, resource/capacity, budget/cost-rollup/
profitability/EVM — see ``services.py`` + the pure calculators). Cross-module reuse: project.client
→ CRM ``customer``; members/skills/timesheets reference HR employees; cost rollup pulls Payroll/
Procurement/Asset/Expense costs (no duplicate masters).
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


PROJECT_OBJECTS: dict[str, dict] = {
    "portfolio": _e("portfolio", "Portfolio", "Portfolios", [
        _f("name", "Name", "text", is_required=True),
        _f("strategic_objectives", "Strategic Objectives", "textarea"),
        _f("investment_allocation", "Investment Allocation", "currency"),
        _sel("health", "Health", "green", "amber", "red"),
        _f("roi", "ROI", "percent"), _st("active", "closed")]),
    "program": _e("program", "Program", "Programs", [
        _f("name", "Name", "text", is_required=True),
        _lk("portfolio", "Portfolio", "portfolio"),
        _f("budget", "Program Budget", "currency"), _f("progress", "Progress", "percent"),
        _f("risks", "Risks", "textarea"), _f("benefits", "Benefits", "textarea"),
        _st("active", "closed")]),
    "project": _e("project", "Project", "Projects", [
        _f("number", "Project Number", "text", is_unique=True),
        _f("name", "Project Name", "text", is_required=True),
        _lk("client", "Client", "customer"),
        _f("description", "Description", "textarea"),
        _lk("program", "Program", "program"),
        _sel("project_type", "Project Type", "internal", "client", "fixed_price", "time_material"),
        _sel("priority", "Priority", "low", "medium", "high", "critical"),
        _f("project_manager", "Project Manager", "user"),
        _f("sponsor", "Sponsor", "user"),
        _f("department", "Department", "text"), _f("cost_center", "Cost Center", "text"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date"),
        _f("planned_budget", "Planned Budget", "currency"),
        _f("actual_cost", "Actual Cost", "currency"),
        _f("forecast_cost", "Forecast Cost", "currency"),
        _f("revenue", "Revenue", "currency"),
        _f("profitability", "Profitability", "currency"),
        _sel("billing_type", "Billing Type", "fixed_price", "time_material", "retainer",
             "milestone"),
        _st("draft", "planned", "active", "on_hold", "completed", "cancelled", "archived")]),
    "project_member": _e("project_member", "Project Member", "Project Members", [
        _lk("project", "Project", "project"), _f("employee", "Employee", "user"),
        _f("role", "Role", "text"), _f("allocation_percent", "Allocation %", "percent"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date")]),
    "employee_skill": _e("employee_skill", "Skill", "Skills", [
        _f("employee", "Employee", "user"), _f("skill", "Skill", "text", is_required=True),
        _sel("level", "Level", "beginner", "intermediate", "advanced", "expert"),
        _f("certification", "Certification", "text"),
        _f("years_experience", "Years Experience", "integer")]),
    "task": _e("task", "Task", "Tasks", [
        _f("number", "Task Number", "text", is_unique=True),
        _lk("project", "Project", "project"),
        _lk("parent_task", "Parent Task", "task"),
        _f("title", "Title", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _sel("task_type", "Type", "task", "story", "bug", "epic", "feature"),
        _f("assignee", "Assignee", "user"),
        _sel("priority", "Priority", "low", "medium", "high", "critical"),
        _f("planned_hours", "Planned Hours", "decimal"),
        _f("actual_hours", "Actual Hours", "decimal"),
        _f("start_date", "Start Date", "date"), _f("due_date", "Due Date", "date"),
        _f("completed_date", "Completed Date", "date"),
        _lk("sprint", "Sprint", "sprint"),
        _st("backlog", "planned", "in_progress", "review", "blocked", "completed", "cancelled")]),
    "milestone": _e("milestone", "Milestone", "Milestones", [
        _lk("project", "Project", "project"), _f("name", "Name", "text", is_required=True),
        _f("due_date", "Due Date", "date"), _f("completion_date", "Completion Date", "date"),
        _f("owner", "Owner", "user"), _st("open", "completed")]),
    "deliverable": _e("deliverable", "Deliverable", "Deliverables", [
        _lk("project", "Project", "project"), _f("name", "Name", "text", is_required=True),
        _f("version", "Version", "text"), _f("owner", "Owner", "user"),
        _f("due_date", "Due Date", "date"),
        _sel("acceptance_status", "Acceptance Status", "pending", "accepted", "rejected")]),
    "task_dependency": _e("task_dependency", "Dependency", "Dependencies", [
        _lk("project", "Project", "project"),
        _lk("predecessor_task", "Predecessor", "task"),
        _lk("successor_task", "Successor", "task"),
        _sel("dependency_type", "Type", "finish_to_start", "start_to_start",
             "finish_to_finish", "start_to_finish"),
        _f("lag_days", "Lag (days)", "integer")]),
    "sprint": _e("sprint", "Sprint", "Sprints", [
        _lk("project", "Project", "project"), _f("name", "Name", "text", is_required=True),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date"),
        _f("goal", "Goal", "textarea"), _f("velocity", "Velocity", "decimal"),
        _st("planned", "active", "completed")]),
    "timesheet": _e("timesheet", "Timesheet", "Timesheets", [
        _lk("project", "Project", "project"), _lk("task", "Task", "task"),
        _f("employee", "Employee", "user"), _f("date", "Date", "date"),
        _f("hours", "Hours", "decimal"), _f("rate", "Rate", "currency"),
        _f("billable", "Billable", "boolean"), _f("notes", "Notes", "textarea"),
        _st("draft", "submitted", "approved", "rejected")]),
    "expense": _e("expense", "Expense", "Expenses", [
        _lk("project", "Project", "project"), _f("employee", "Employee", "user"),
        _sel("category", "Category", "travel", "meals", "accommodation", "misc"),
        _f("amount", "Amount", "currency"), _f("date", "Date", "date"),
        _st("draft", "submitted", "approved", "rejected")]),
    "risk": _e("risk", "Risk", "Risks", [
        _lk("project", "Project", "project"), _f("title", "Title", "text", is_required=True),
        _sel("probability", "Probability", "low", "medium", "high"),
        _sel("impact", "Impact", "low", "medium", "high"),
        _f("mitigation", "Mitigation", "textarea"), _f("owner", "Owner", "user"),
        _f("response_plan", "Response Plan", "textarea"),
        _st("open", "mitigated", "closed")]),
    "issue": _e("issue", "Issue", "Issues", [
        _lk("project", "Project", "project"), _f("title", "Title", "text", is_required=True),
        _sel("severity", "Severity", "low", "medium", "high", "critical"),
        _sel("priority", "Priority", "low", "medium", "high"),
        _f("root_cause", "Root Cause", "textarea"), _f("resolution", "Resolution", "textarea"),
        _st("open", "in_progress", "resolved", "closed")]),
    "change_request": _e("change_request", "Change Request", "Change Requests", [
        _lk("project", "Project", "project"), _f("title", "Title", "text", is_required=True),
        _f("scope_impact", "Scope Impact", "textarea"),
        _f("cost_impact", "Cost Impact", "currency"),
        _f("schedule_impact_days", "Schedule Impact (days)", "integer"),
        _f("risk_impact", "Risk Impact", "textarea"),
        _st("draft", "pending", "approved", "rejected")]),
    "quality_review": _e("quality_review", "Quality Review", "Quality Reviews", [
        _lk("project", "Project", "project"), _f("name", "Name", "text", is_required=True),
        _sel("review_type", "Type", "review", "defect", "test"),
        _sel("result", "Result", "passed", "failed", "requires_attention"),
        _f("notes", "Notes", "textarea")]),
}

PROJECT_SEQUENCES = {
    "project": {"name": "Project", "prefix": "PRJ-", "padding": 6},
    "task": {"name": "Task", "prefix": "TSK-", "padding": 6},
}
EVENT_KEY = {"project": "project", "task": "task"}
_MAIN = list(PROJECT_OBJECTS.keys())


# ── workflows ────────────────────────────────────────────────────────────────
def _wf(slug, name, entity_slug, notify="task_assigned", trigger_type="record_created"):
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


PROJECT_WORKFLOWS = [
    _wf("project_approval", "Project Approval", "project", "milestone_due"),
    _wf("budget_approval", "Budget Approval", "project", "budget_exceeded",
        trigger_type="record_updated"),
    _wf("timesheet_approval", "Timesheet Approval", "timesheet", "task_assigned"),
    _wf("expense_approval", "Expense Approval", "expense", "task_assigned"),
    _wf("change_request_approval", "Change Request Approval", "change_request", "milestone_due"),
    _wf("deliverable_approval", "Deliverable Approval", "deliverable", "milestone_due"),
    _wf("milestone_approval", "Milestone Approval", "milestone", "milestone_due",
        trigger_type="record_updated"),
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
PROJECT_ROLES = [
    _role("project_administrator", "Project Administrator", "Full access.",
          [(None, _FULL + ["admin"])]),
    _role("pmo_manager", "PMO Manager", "Portfolio/program oversight.", [(None, _FULL)]),
    _role("project_manager", "Project Manager", "Run projects.",
          [("project", _FULL), ("task", _FULL), ("milestone", _FULL), ("risk", _FULL),
           ("issue", _FULL), ("change_request", _FULL), ("project_member", _FULL),
           ("timesheet", ["read", "update"]), ("expense", ["read", "update"])]),
    _role("team_lead", "Team Lead", "Lead a team.",
          [("task", _FULL), ("timesheet", ["read", "update"]), ("project", ["read"])]),
    _role("team_member", "Team Member", "Work tasks + log time.",
          [("task", ["read", "update"]), ("timesheet", ["create", "read"]),
           ("expense", ["create", "read"]), ("project", ["read"])]),
    _role("project_executive", "Executive", "Read dashboards/reports.", [(None, ["read"])]),
    _role("project_client", "Client", "Client portal visibility.",
          [("project", ["read"]), ("milestone", ["read"]), ("deliverable", ["read", "update"]),
           ("issue", ["create", "read"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


PROJECT_REPORTS = [
    _report("project_register", "Project Register", "project"),
    _report("portfolio_summary", "Portfolio Summary", "portfolio", "pivot"),
    _report("program_summary", "Program Summary", "program", "pivot"),
    _report("resource_utilization", "Resource Utilization", "project_member", "pivot"),
    _report("capacity_report", "Capacity Report", "project_member", "pivot"),
    _report("timesheet_summary", "Timesheet Summary", "timesheet", "pivot"),
    _report("budget_report", "Budget Report", "project", "pivot"),
    _report("profitability_report", "Profitability Report", "project", "pivot"),
    _report("earned_value_report", "Earned Value Report", "project"),
    _report("risk_register", "Risk Register", "risk"),
    _report("issue_register", "Issue Register", "issue"),
    _report("change_log", "Change Log", "change_request"),
    _report("sprint_report", "Sprint Report", "sprint"),
    _report("velocity_report", "Velocity Report", "sprint", "pivot"),
    _report("burndown_report", "Burndown Report", "task", "pivot"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


PROJECT_DASHBOARDS = [
    {"slug": "project_executive_dashboard", "name": "Executive Dashboard", "is_default": True,
     "widgets": [
         _w("metric_card", "Active Projects", 0, 0, 3, 2),
         _w("metric_card", "Budget Variance", 3, 0, 3, 2),
         _w("metric_card", "Profitability", 6, 0, 3, 2),
         _w("report", "Project Register", 0, 2, 6, 4, report_slug="project_register"),
         _w("report", "Resource Utilization", 6, 2, 6, 4, report_slug="resource_utilization"),
     ]},
    {"slug": "project_pm_dashboard", "name": "PM Dashboard", "widgets": [
        _w("report", "Risks", 0, 0, 6, 4, report_slug="risk_register"),
        _w("report", "Issues", 6, 0, 6, 4, report_slug="issue_register"),
        _w("report", "Budget", 0, 4, 6, 4, report_slug="budget_report"),
    ]},
    {"slug": "project_agile_dashboard", "name": "Agile Dashboard", "widgets": [
        _w("report", "Velocity", 0, 0, 6, 4, report_slug="velocity_report"),
        _w("report", "Burndown", 6, 0, 6, 4, report_slug="burndown_report"),
        _w("report", "Sprints", 0, 4, 6, 4, report_slug="sprint_report"),
    ]},
]

PROJECT_NOTIFICATIONS = [
    {"slug": s, "name": n, "channels": ["in_app"], "subject_template": n, "body_template": n + "."}
    for s, n in [
        ("task_assigned", "Task Assigned"), ("task_overdue", "Task Overdue"),
        ("sprint_ending", "Sprint Ending"), ("milestone_due", "Milestone Due"),
        ("budget_exceeded", "Budget Exceeded"), ("resource_conflict", "Resource Conflict"),
    ]
]


# ── forms / views / app ──────────────────────────────────────────────────────
def _form_for(slug):
    obj = PROJECT_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = PROJECT_OBJECTS[slug]
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if any(f["slug"] == "status" for f in obj["fields"]):
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


_NAV = [
    ("Delivery", ["portfolio", "program", "project"]),
    ("Work", ["task", "milestone", "deliverable", "sprint", "task_dependency"]),
    ("People", ["project_member", "employee_skill", "timesheet", "expense"]),
    ("Governance", ["risk", "issue", "change_request", "quality_review"]),
]


def build_projects_manifest() -> dict:
    return {
        "schema_version": 1,
        "entities": list(PROJECT_OBJECTS.values()),
        "forms": [_form_for(s) for s in PROJECT_OBJECTS],
        "views": [v for s in PROJECT_OBJECTS for v in _views_for(s)],
        "workflows": PROJECT_WORKFLOWS,
        "reports": PROJECT_REPORTS,
        "notification_templates": PROJECT_NOTIFICATIONS,
        "roles": PROJECT_ROLES,
        "dashboards": PROJECT_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "Projects Menu", "scope": "app",
            "tree": [{"label": label, "items": [
                {"label": PROJECT_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                for s in items]} for label, items in _NAV],
        }],
        "home_layouts": [{"ref": "home", "name": "Projects Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Project Management"}]}],
        "applications": [{
            "slug": "projects", "name": "Projects & PSA", "icon": "FolderKanban",
            "color": "#4f46e5", "included_entity_slugs": _MAIN, "navigation_ref": "main",
            "home_layout_ref": "home", "role_slugs": [r["slug"] for r in PROJECT_ROLES],
            "is_published": True,
        }],
    }


def seed_projects_template():
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="projects",
        defaults={
            "name": "Projects & PSA",
            "category": "Projects",
            "description": "Enterprise project management + professional services automation — "
                           "portfolios, programs, projects, tasks, sprints, timesheets, expenses, "
                           "risks/issues/change requests with native scheduling, resource, budget, "
                           "cost-rollup, profitability and earned-value engines.",
            "icon": "FolderKanban", "color": "#4f46e5", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_projects_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
