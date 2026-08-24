"""
HR (Human Capital Management) Solution blueprint (Phase P2.7).

A complete employee-lifecycle platform — Organization Structure, Recruitment, Employee Core,
Onboarding, Attendance, Leave, Performance, Promotions/Transfers, Offboarding — expressed as
ONE curated extended manifest and installed through the P2.4A Solution Template Framework.
Native code (``services.py``) is a thin lifecycle layer over the reusable
``SolutionDocumentService``; HR ships almost 100% framework. Employee carries the
payroll-compatible structure (employee_number/cost_center/pay_grade/department/employment_type/
hire_date/manager/branch) so P2.8 Payroll needs no HR redesign.
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


def _code(label="Code"):
    return _f("code", label, "text", is_unique=True)


# ── business objects (9 modules) ─────────────────────────────────────────────
HR_OBJECTS: dict[str, dict] = {
    # Module 1 — Organization Structure
    "branch": _e("branch", "Branch", "Branches", [
        _code("Branch Code"), _f("name", "Branch Name", "text", is_required=True),
        _f("address", "Address", "textarea"), _f("country", "Country", "text"),
        _f("timezone", "Timezone", "text"), _st("active", "inactive")]),
    "division": _e("division", "Division", "Divisions", [
        _code("Division Code"), _f("name", "Division Name", "text", is_required=True),
        _f("description", "Description", "textarea"), _lk("branch", "Branch", "branch"),
        _f("head", "Head Of Division", "user"), _st("active", "inactive")]),
    "department": _e("department", "Department", "Departments", [
        _code("Department Code"), _f("name", "Department Name", "text", is_required=True),
        _f("description", "Description", "textarea"), _lk("division", "Division", "division"),
        _f("manager", "Manager", "user"), _f("cost_center", "Cost Center", "text"),
        _lk("parent_department", "Parent Department", "department"), _st("active", "inactive")]),
    "team": _e("team", "Team", "Teams", [
        _code("Team Code"), _f("name", "Team Name", "text", is_required=True),
        _lk("department", "Department", "department"), _f("team_lead", "Team Lead", "user"),
        _f("description", "Description", "textarea"), _st("active", "inactive")]),
    "position": _e("position", "Position", "Positions", [
        _code("Position Code"), _f("name", "Position Name", "text", is_required=True),
        _lk("department", "Department", "department"),
        _lk("job_family", "Job Family", "job_family"),
        _lk("job_grade", "Job Grade", "job_grade"),
        _lk("reports_to", "Reports To", "position"), _st("active", "inactive")]),
    "job_family": _e("job_family", "Job Family", "Job Families", [
        _code(), _f("name", "Name", "text", is_required=True),
        _f("description", "Description", "textarea")]),
    "job_grade": _e("job_grade", "Job Grade", "Job Grades", [
        _code(), _f("name", "Name", "text", is_required=True),
        _f("description", "Description", "textarea")]),

    # Module 2 — Recruitment
    "candidate": _e("candidate", "Candidate", "Candidates", [
        _f("number", "Candidate Number", "text", is_unique=True),
        _f("first_name", "First Name", "text"),
        _f("last_name", "Last Name", "text", is_required=True),
        _f("email", "Email", "email"), _f("phone", "Phone", "phone"),
        _sel("source", "Source", "web", "referral", "agency", "event", "other"),
        _lk("position_applied", "Position Applied", "position"),
        _f("resume", "Resume", "file"),
        _st("new", "screening", "interview", "offer", "hired", "rejected")]),
    "interview": _e("interview", "Interview", "Interviews", [
        _f("number", "Interview Number", "text", is_unique=True),
        _lk("candidate", "Candidate", "candidate"),
        _f("interviewer", "Interviewer", "user"), _f("date", "Date", "datetime"),
        _sel("type", "Type", "technical", "hr", "managerial", "final"),
        _f("feedback", "Feedback", "textarea"), _f("rating", "Rating", "rating"),
        _st("scheduled", "completed", "cancelled")]),
    "offer": _e("offer", "Offer", "Offers", [
        _f("number", "Offer Number", "text", is_unique=True),
        _lk("candidate", "Candidate", "candidate"), _lk("position", "Position", "position"),
        _f("salary", "Salary", "currency"), _f("offer_date", "Offer Date", "date"),
        _st("draft", "sent", "accepted", "rejected")]),

    # Module 3 — Employee Core (payroll-compatible)
    "employee": _e("employee", "Employee", "Employees", [
        _f("number", "Employee Number", "text", is_unique=True),
        _f("first_name", "First Name", "text"),
        _f("last_name", "Last Name", "text", is_required=True),
        _f("email", "Email", "email"), _f("phone", "Phone", "phone"),
        _f("hire_date", "Hire Date", "date"),
        _sel("employment_type", "Employment Type", "permanent", "contract", "internship",
             "part_time", "consultant"),
        _st("active", "probation", "suspended", "inactive", "terminated"),
        _lk("manager", "Manager", "employee"), _lk("department", "Department", "department"),
        _lk("team", "Team", "team"), _lk("position", "Position", "position"),
        _lk("branch", "Branch", "branch"), _f("cost_center", "Cost Center", "text"),
        _lk("pay_grade", "Pay Grade", "job_grade")]),

    # Module 4 — Onboarding
    "onboarding_plan": _e("onboarding_plan", "Onboarding Plan", "Onboarding Plans", [
        _lk("employee", "Employee", "employee"), _f("start_date", "Start Date", "date"),
        _st("draft", "in_progress", "completed")]),
    "onboarding_task": _e("onboarding_task", "Onboarding Task", "Onboarding Tasks", [
        _lk("onboarding_plan", "Onboarding Plan", "onboarding_plan"),
        _f("name", "Task", "text", is_required=True),
        _sel("category", "Category", "equipment", "access", "orientation", "policy", "other"),
        _f("assignee", "Assignee", "user"), _st("open", "completed")]),

    # Module 5 — Attendance (integration source designed in now)
    "shift": _e("shift", "Shift", "Shifts", [
        _f("name", "Shift Name", "text", is_required=True),
        _f("start_time", "Start Time", "time"), _f("end_time", "End Time", "time"),
        _f("break_minutes", "Break (minutes)", "integer")]),
    "attendance_record": _e("attendance_record", "Attendance Record", "Attendance Records", [
        _lk("employee", "Employee", "employee"), _f("date", "Date", "date"),
        _f("check_in", "Check In", "datetime"), _f("check_out", "Check Out", "datetime"),
        _lk("shift", "Shift", "shift"),
        _st("present", "absent", "late", "half_day", "remote"),
        _sel("source", "Source", "manual", "biometric", "rfid", "mobile", "gps")]),

    # Module 6 — Leave
    "leave_type": _e("leave_type", "Leave Type", "Leave Types", [
        _code(), _f("name", "Name", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _f("default_days", "Default Days", "decimal")]),
    "leave_balance": _e("leave_balance", "Leave Balance", "Leave Balances", [
        _lk("employee", "Employee", "employee"), _lk("leave_type", "Leave Type", "leave_type"),
        _f("allocated", "Allocated", "decimal"), _f("used", "Used", "decimal"),
        _f("remaining", "Remaining", "decimal"), _f("year", "Year", "integer")]),
    "leave_request": _e("leave_request", "Leave Request", "Leave Requests", [
        _lk("employee", "Employee", "employee"), _lk("leave_type", "Leave Type", "leave_type"),
        _lk("leave_balance", "Leave Balance", "leave_balance"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date"),
        _f("days", "Days", "decimal"), _f("reason", "Reason", "textarea"),
        _st("draft", "pending", "approved", "rejected")]),
    "holiday_calendar": _e("holiday_calendar", "Holiday", "Holidays", [
        _f("name", "Name", "text", is_required=True), _f("date", "Date", "date"),
        _f("country", "Country", "text"),
        _sel("type", "Type", "country", "company", "regional")]),

    # Module 7 — Performance
    "review_cycle": _e("review_cycle", "Review Cycle", "Review Cycles", [
        _f("name", "Name", "text", is_required=True),
        _sel("type", "Type", "quarterly", "half_yearly", "annual"),
        _f("start_date", "Start Date", "date"), _f("end_date", "End Date", "date")]),
    "goal": _e("goal", "Goal", "Goals", [
        _lk("employee", "Employee", "employee"),
        _lk("review_cycle", "Review Cycle", "review_cycle"),
        _f("period", "Period", "text"), _f("target", "Target", "textarea")]),
    "kpi": _e("kpi", "KPI", "KPIs", [
        _lk("goal", "Goal", "goal"), _f("name", "Name", "text", is_required=True),
        _f("weight", "Weight", "percent"), _f("measurement", "Measurement", "text")]),
    "performance_review": _e("performance_review", "Performance Review", "Performance Reviews", [
        _lk("employee", "Employee", "employee"),
        _lk("review_cycle", "Review Cycle", "review_cycle"),
        _f("rating", "Rating", "rating"), _f("summary", "Summary", "textarea"),
        _st("goal_setting", "employee_review", "manager_review", "completed")]),

    # Module 8 — Promotions & Transfers
    "promotion": _e("promotion", "Promotion", "Promotions", [
        _lk("employee", "Employee", "employee"),
        _lk("current_position", "Current Position", "position"),
        _lk("new_position", "New Position", "position"),
        _f("effective_date", "Effective Date", "date"), _st("draft", "approved")]),
    "transfer": _e("transfer", "Transfer", "Transfers", [
        _lk("employee", "Employee", "employee"),
        _lk("current_department", "Current Department", "department"),
        _lk("new_department", "New Department", "department"),
        _f("effective_date", "Effective Date", "date"), _st("draft", "approved")]),

    # Module 9 — Offboarding
    "exit_request": _e("exit_request", "Exit Request", "Exit Requests", [
        _lk("employee", "Employee", "employee"), _f("reason", "Reason", "textarea"),
        _f("last_working_day", "Last Working Day", "date"),
        _st("draft", "approved", "completed")]),
    "asset_return": _e("asset_return", "Asset Return", "Asset Returns", [
        _lk("exit_request", "Exit Request", "exit_request"),
        _f("asset", "Asset", "text"), _f("returned", "Returned", "boolean"),
        _f("notes", "Notes", "text")]),
    "clearance": _e("clearance", "Clearance", "Clearances", [
        _lk("exit_request", "Exit Request", "exit_request"),
        _sel("department", "Department", "hr", "it", "finance", "facilities"),
        _f("cleared", "Cleared", "boolean"), _f("notes", "Notes", "text")]),
}

HR_SEQUENCES = {
    "candidate": {"name": "Candidate", "prefix": "CAN-", "padding": 6},
    "interview": {"name": "Interview", "prefix": "INT-", "padding": 6},
    "offer": {"name": "Offer", "prefix": "OFF-", "padding": 6},
    "employee": {"name": "Employee", "prefix": "EMP-", "padding": 6},
}
EVENT_KEY = {"candidate": "candidate", "interview": "interview", "offer": "offer",
             "employee": "employee", "leave_request": "leave",
             "performance_review": "performance"}
_MAIN = list(HR_OBJECTS.keys())


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


def _notify_only(notify):
    return ([{"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
              "is_entry": True, "config": {"template_slug": notify}}], [])


HR_WORKFLOWS = [
    _wf("hiring_workflow", "Hiring Workflow", "candidate", *_notify_only("interview_scheduled")),
    _wf("interview_workflow", "Interview Workflow", "interview",
        *_notify_only("interview_scheduled")),
    _wf("offer_approval", "Offer Approval", "offer", *_approval("offer_sent")),
    _wf("onboarding_workflow", "Onboarding Workflow", "employee",
        *_notify_only("offer_accepted")),
    _wf("leave_approval", "Leave Approval", "leave_request", *_approval("leave_approved")),
    _wf("attendance_approval", "Attendance Approval", "attendance_record",
        *_notify_only("review_due")),
    _wf("performance_review_wf", "Performance Review", "performance_review",
        *_approval("review_due")),
    _wf("promotion_approval", "Promotion Approval", "promotion", *_approval("review_due")),
    _wf("transfer_approval", "Transfer Approval", "transfer", *_approval("review_due")),
    _wf("offboarding_workflow", "Offboarding Workflow", "exit_request",
        *_approval("review_due")),
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
HR_ROLES = [
    _role("hr_administrator", "HR Administrator", "Full HR access.", [(None, _FULL + ["admin"])]),
    _role("hr_manager", "HR Manager", "People operations.", [(None, _FULL)]),
    _role("recruiter", "Recruiter", "Recruitment.",
          [("candidate", _FULL), ("interview", _FULL), ("offer", _FULL),
           ("position", ["read"])]),
    _role("hr_line_manager", "Manager", "Approvals and reviews.",
          [("employee", ["read"]), ("leave_request", ["read", "update"]),
           ("performance_review", ["read", "update"]), ("attendance_record", ["read", "update"]),
           ("promotion", ["read", "update"]), ("transfer", ["read", "update"])]),
    _role("hr_employee", "Employee", "Self-service.",
          [(None, ["read"]), ("leave_request", ["create", "read"]),
           ("attendance_record", ["create", "read"])]),
]


# ── reports + dashboards ─────────────────────────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


HR_REPORTS = [
    _report("employee_directory", "Employee Directory", "employee"),
    _report("organization_directory", "Organization Directory", "department"),
    _report("attendance_summary", "Attendance Summary", "attendance_record", "pivot"),
    _report("leave_balance_report", "Leave Balance Report", "leave_balance"),
    _report("attrition_report", "Attrition Report", "employee", "pivot"),
    _report("hiring_funnel_report", "Hiring Funnel Report", "candidate", "funnel"),
    _report("performance_report", "Performance Report", "performance_review"),
    _report("promotion_history", "Promotion History", "promotion"),
    _report("transfer_history", "Transfer History", "transfer"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


HR_DASHBOARDS = [
    {"slug": "hr_executive_dashboard", "name": "HR Executive Dashboard", "is_default": True,
     "widgets": [
         _w("metric_card", "Total Employees", 0, 0, 3, 2),
         _w("metric_card", "Attrition Rate", 3, 0, 3, 2),
         _w("metric_card", "Open Positions", 6, 0, 3, 2),
         _w("report", "Hiring Funnel", 0, 2, 6, 4, report_slug="hiring_funnel_report"),
         _w("report", "Leave Trends", 6, 2, 6, 4, report_slug="leave_balance_report"),
     ]},
    {"slug": "workforce_dashboard", "name": "Workforce Dashboard", "widgets": [
        _w("metric_card", "Attendance Rate", 0, 0, 3, 2),
        _w("report", "Headcount by Department", 3, 0, 6, 4,
           report_slug="organization_directory"),
        _w("report", "Upcoming Reviews", 0, 2, 6, 4, report_slug="performance_report"),
    ]},
]

HR_NOTIFICATIONS = [
    {"slug": s, "name": n, "channels": ["in_app"], "subject_template": n,
     "body_template": n + "."}
    for s, n in [
        ("interview_scheduled", "Interview Scheduled"), ("offer_sent", "Offer Sent"),
        ("offer_accepted", "Offer Accepted"), ("leave_approved", "Leave Approved"),
        ("leave_rejected", "Leave Rejected"), ("review_due", "Review Due"),
        ("probation_ending", "Probation Ending"), ("birthday", "Birthday"),
        ("work_anniversary", "Work Anniversary"),
    ]
]


# ── forms / views / app ──────────────────────────────────────────────────────
def _form_for(slug):
    obj = HR_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = HR_OBJECTS[slug]
    field_slugs = {f["slug"] for f in obj["fields"]}
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if "status" in field_slugs:
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


# Navigation grouped by module (org charts render via the generic Tree/Org view over the
# department.parent_department + employee.manager hierarchies — no special entity needed).
_NAV = [
    ("Organization", ["branch", "division", "department", "team", "position",
                      "job_family", "job_grade"]),
    ("Recruitment", ["candidate", "interview", "offer"]),
    ("People", ["employee", "onboarding_plan"]),
    ("Time", ["attendance_record", "shift", "leave_request", "leave_type",
              "leave_balance", "holiday_calendar"]),
    ("Performance", ["review_cycle", "goal", "performance_review"]),
    ("Lifecycle", ["promotion", "transfer", "exit_request"]),
]


def build_hr_manifest() -> dict:
    return {
        "schema_version": 1,
        "entities": list(HR_OBJECTS.values()),
        "forms": [_form_for(s) for s in HR_OBJECTS],
        "views": [v for s in HR_OBJECTS for v in _views_for(s)],
        "workflows": HR_WORKFLOWS,
        "reports": HR_REPORTS,
        "notification_templates": HR_NOTIFICATIONS,
        "roles": HR_ROLES,
        "dashboards": HR_DASHBOARDS,
        "navigations": [{
            "ref": "main", "name": "HR Menu", "scope": "app",
            "tree": [{"label": label, "items": [
                {"label": HR_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
                for s in items]} for label, items in _NAV],
        }],
        "home_layouts": [{"ref": "home", "name": "HR Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Human Resources"}]}],
        "applications": [{
            "slug": "hr", "name": "Human Resources", "icon": "UsersRound", "color": "#0d9488",
            "included_entity_slugs": _MAIN, "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in HR_ROLES], "is_published": True,
        }],
    }


def seed_hr_template():
    """Upsert the published, system HR SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="hr",
        defaults={
            "name": "Human Resources",
            "category": "HR",
            "description": "Complete HCM — organization structure, recruitment, employees, "
                           "onboarding, attendance, leave, performance, promotions/transfers and "
                           "offboarding with workflows, roles, dashboards and reports. "
                           "Payroll-ready employee structure.",
            "icon": "UsersRound", "color": "#0d9488", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_hr_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
