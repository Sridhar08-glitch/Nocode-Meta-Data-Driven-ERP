"""
College package — Phase C1 (Academic Core) certification.

The 2nd education package. Pure manifest: every assertion is about manifest provisioning + reuse
of ERP Core engines (metadata/workflow/RBAC/reporting/analytics/dashboards) — zero native code.
Validates the reuse contract (COLLEGE_ARCHITECTURE_ANALYSIS.md §9) + coexistence with School.
"""
import uuid

import pytest

from apps.college.blueprint import build_college_manifest, seed_college_template
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.reporting.models import Dashboard, Report
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member
from apps.solution_templates.models import InstalledSolution
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.workflows.models import WorkflowDefinition

C1_ENTITIES = [
    "campus", "academic_year", "term", "academic_calendar_event", "faculty", "department",
    "program", "specialization", "course", "prerequisite", "instructor", "course_section",
    "curriculum", "curriculum_course", "student", "program_enrollment",
]


@pytest.fixture
def template(db):
    return seed_college_template()


def _rec(ws, member, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=member, entity=entity, data=data)


# ── manifest + provisioning ──────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_package_metadata():
    pkg = build_college_manifest()["package"]
    assert pkg["slug"] == "college" and pkg["version"] == "1.0.0"
    assert "higher_education" in pkg["provides_capabilities"]


@pytest.mark.django_db
def test_install_provisions_academic_core(template):
    ws = uuid.uuid4()
    installed = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert installed.installed_version == "1.0.0"
    for slug in C1_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for role in ["college_administrator", "registrar", "dean", "department_head", "instructor"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["executive_dashboard", "registrar_dashboard", "academic_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    assert Report.objects.filter(workspace_id=ws, slug="enrollment_report").exists()
    assert Application.objects.filter(workspace_id=ws, slug="college").exists()
    assert WorkflowDefinition.objects.filter(
        workspace_id=ws, slug="program_enrollment_activated").exists()


# ── reuse: workflow, role dashboards (DG-5), analytics KPI ────────────────────
@pytest.mark.django_db
def test_program_enrollment_marks_student_enrolled(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "degree_type": "bachelor",
                                        "status": "active"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "status": "applicant"})
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "program_enrollment",
             {"student": str(student["id"]), "program": str(prog["id"]), "status": "active"})
    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    refreshed = RecordService.retrieve_record(workspace_id=ws, member=member,
                                              entity=student_entity, record_id=student["id"])
    assert refreshed["status"] == "enrolled"   # related-record update via reused workflow engine


@pytest.mark.django_db
def test_role_dashboards_auto_route(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    registrar = Role.objects.get(workspace_id=ws, slug="registrar")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(registrar.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "registrar_dashboard"


@pytest.mark.django_db
def test_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    _rec(ws, member, "student", {"first_name": "A", "status": "enrolled"})
    _rec(ws, member, "student", {"first_name": "B", "status": "enrolled"})
    _rec(ws, member, "student", {"first_name": "C", "status": "applicant"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="enrolled_students")
    result = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert int(float(result["value"])) == 2


# ── package lifecycle + coexistence with School (frozen) ─────────────────────
@pytest.mark.django_db
def test_college_coexists_with_crm():
    """Realistic single-workspace coexistence: College + an unrelated horizontal package (CRM).
    (School and College are ALTERNATIVE education verticals — a tenant installs one, not both;
    their shared academic-spine slugs are exactly why an Academic Base — installed once — is the
    right future architecture, see COLLEGE_ARCHITECTURE_ANALYSIS.md §5.)"""
    from apps.crm.blueprint import seed_crm_template
    ws = uuid.uuid4()
    sol.install(template_id=seed_crm_template().id, workspace_id=ws, installed_by=None)
    sol.install(template_id=seed_college_template().id, workspace_id=ws, installed_by=None)
    assert InstalledSolution.objects.filter(workspace_id=ws, status="active").count() == 2
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="program").exists()   # college
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="lead").exists()      # crm


@pytest.mark.django_db
def test_school_and_college_install_in_separate_workspaces():
    """Both education packages are catalog-coexistent: each installs cleanly into its OWN
    workspace (the real deployment model — different institution types)."""
    from apps.school.blueprint import seed_school_template
    ws_school, ws_college = uuid.uuid4(), uuid.uuid4()
    sol.install(template_id=seed_school_template().id, workspace_id=ws_school, installed_by=None)
    sol.install(template_id=seed_college_template().id, workspace_id=ws_college, installed_by=None)
    assert EntityDefinition.objects.filter(workspace_id=ws_school, slug="grade_level").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws_college, slug="program").exists()
    # no cross-workspace bleed
    assert not EntityDefinition.objects.filter(workspace_id=ws_college, slug="grade_level").exists()


@pytest.mark.django_db
def test_lifecycle_disable_enable(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    sol.uninstall(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert InstalledSolution.objects.get(id=inst.id).status == "disabled"
    sol.enable(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert InstalledSolution.objects.get(id=inst.id).status == "active"


@pytest.mark.django_db
def test_seed_idempotent():
    seed_college_template()
    seed_college_template()
    from apps.solution_templates.models import SolutionTemplate
    assert SolutionTemplate.objects.filter(slug="college").count() == 1


@pytest.mark.django_db
def test_nav_wires_academic_core(template):
    m = build_college_manifest()
    nav_targets = {item["target"] for grp in m["navigations"][0]["tree"] for item in grp["items"]}
    for slug in ["program", "course", "course_section", "student", "program_enrollment"]:
        assert slug in nav_targets, slug
    assert set(C1_ENTITIES) <= set(m["applications"][0]["included_entity_slugs"])


# ══ C2 — Course Registration (first manifest consumer of the Core Guard Framework) ══
C2_ENTITIES = ["registration_period", "registration_hold", "registration", "waitlist_entry"]


def _c2_setup(ws, member, *, capacity=2, max_credits=30):
    """Provision a program (with per-term credit ceiling), term, course, section + student."""
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS",
                                        "degree_type": "bachelor", "status": "active",
                                        "max_credits_per_term": max_credits})
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester",
                                     "status": "active"})
    course = _rec(ws, member, "course", {"name": "Intro CS", "code": "CS101", "credit_hours": 3})
    section = _rec(ws, member, "course_section", {"course": str(course["id"]),
                                                  "term": str(term["id"]),
                                                  "capacity": capacity, "status": "open"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "status": "enrolled"})
    return {"program": prog, "term": term, "course": course, "section": section,
            "student": student}


def _register(ws, member, ctx, on_commit, *, student=None, section=None, credits=3):
    with on_commit(execute=True):
        reg = _rec(ws, member, "registration", {
            "student": str((student or ctx["student"])["id"]),
            "program": str(ctx["program"]["id"]),
            "course": str(ctx["course"]["id"]),
            "course_section": str((section or ctx["section"])["id"]),
            "term": str(ctx["term"]["id"]),
            "credit_hours": credits, "status": "confirmed"})
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="registration")
    return RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                          record_id=reg["id"])["status"]


def test_c2_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c2_declares_guard_capability():
    pkg = build_college_manifest()["package"]
    assert "cross_record_validation" in pkg["requires_capabilities"]
    assert "course_registration" in pkg["provides_capabilities"]


@pytest.mark.django_db
def test_c2_install_provisions_registration(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C2_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(
        workspace_id=ws, slug="registration_eligibility").exists()
    assert Role.objects.filter(workspace_id=ws, slug="academic_advisor").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="registration_dashboard").exists()


@pytest.mark.django_db
def test_c2_guard_is_pure_manifest_no_native_code(template):
    """The eligibility workflow's step config carries only guard RULES — enforcement is the Core
    GuardService (action_guard). No College code evaluates the constraint."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.workflows.models import WorkflowStep
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="registration_eligibility")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    names = {g["name"] for g in step.config["guards"]}
    assert names == {"capacity", "credit_limit", "no_active_hold"}


@pytest.mark.django_db
def test_c2_registration_confirmed_within_limits(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _c2_setup(ws, member, capacity=2, max_credits=30)
    status = _register(ws, member, ctx, django_capture_on_commit_callbacks)
    assert status == "confirmed"   # capacity ok, credits ok, no hold → guard true


@pytest.mark.django_db
def test_c2_guard_waitlists_when_section_full(template, django_capture_on_commit_callbacks):
    """Capacity is a DYNAMIC threshold read from course_section — no denormalised counter."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _c2_setup(ws, member, capacity=1, max_credits=30)
    s1 = _register(ws, member, ctx, django_capture_on_commit_callbacks,
                   student=ctx["student"])
    assert s1 == "confirmed"                                   # 1 <= capacity 1
    other = _rec(ws, member, "student", {"first_name": "Bo", "program": str(ctx["program"]["id"]),
                                         "status": "enrolled"})
    s2 = _register(ws, member, ctx, django_capture_on_commit_callbacks, student=other)
    assert s2 == "waitlisted"                                  # 2 !<= 1 → guard false → waitlist


@pytest.mark.django_db
def test_c2_guard_waitlists_when_credit_limit_exceeded(
        template, django_capture_on_commit_callbacks):
    """Per-term credit SUM vs the program's max_credits_per_term (dynamic threshold)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _c2_setup(ws, member, capacity=10, max_credits=3)
    s1 = _register(ws, member, ctx, django_capture_on_commit_callbacks, credits=3)
    assert s1 == "confirmed"                                   # sum 3 <= 3
    # A second section in the same term so capacity never interferes.
    section2 = _rec(ws, member, "course_section", {"course": str(ctx["course"]["id"]),
                                                   "term": str(ctx["term"]["id"]),
                                                   "capacity": 10, "status": "open"})
    s2 = _register(ws, member, ctx, django_capture_on_commit_callbacks,
                   section=section2, credits=3)
    assert s2 == "waitlisted"                                  # sum 6 !<= 3 → guard false


@pytest.mark.django_db
def test_c2_guard_waitlists_when_active_hold(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _c2_setup(ws, member, capacity=10, max_credits=30)
    _rec(ws, member, "registration_hold", {"student": str(ctx["student"]["id"]),
                                            "hold_type": "financial", "status": "active"})
    status = _register(ws, member, ctx, django_capture_on_commit_callbacks)
    assert status == "waitlisted"                              # active hold → not_exists fails


# ══ C3 — Assessment / Grades / GPA / CGPA / Standing / Degree Progress ═══════════
# Every calculation below is Core ``action_aggregate`` config in the manifest — College writes ZERO
# GPA/standing/progress code. These tests prove the credit-weighted aggregates end-to-end.
C3_ENTITIES = ["grade_scheme", "grade_scale", "assessment", "assessment_result", "course_result",
               "semester_result", "student_academic_record", "degree_progress", "transfer_credit",
               "graduation_application"]


def _retrieve(ws, member, slug, rid):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                         record_id=rid)


def _update(ws, member, slug, rid, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.update_record(workspace_id=ws, member=member, entity=entity,
                                       record_id=rid, data=data)


def _grade_scale(ws, member):
    scheme = _rec(ws, member, "grade_scheme",
                  {"name": "Standard 4.0", "code": "STD4", "status": "active", "is_default": True})
    for letter, gp in [("A", 4.0), ("B", 3.0), ("C", 2.0), ("D", 1.0), ("F", 0.0)]:
        _rec(ws, member, "grade_scale", {"grade_scheme": str(scheme["id"]), "letter": letter,
                                         "grade_points": gp, "is_passing": letter != "F"})
    return scheme


def _c3_base(ws, member, *, total_credits_required=120):
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "degree_type": "bachelor",
                                        "status": "active", "max_credits_per_term": 30,
                                        "total_credits_required": total_credits_required})
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester", "status": "active"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "status": "enrolled"})
    return {"program": prog, "term": term, "student": student}


def _result(ws, member, base, *, credit_hours, grade_points, letter="A", status="published",
            term=None, course_code=None):
    """Create a course_result with grade_points set → quality_points (formula) auto-computes."""
    import uuid as _u
    code = course_code or f"C{_u.uuid4().hex[:6]}"
    course = _rec(ws, member, "course", {"name": code, "code": code, "credit_hours": credit_hours})
    return _rec(ws, member, "course_result", {
        "student": str(base["student"]["id"]), "program": str(base["program"]["id"]),
        "term": str((term or base["term"])["id"]), "course": str(course["id"]),
        "credit_hours": credit_hours, "grade_points": grade_points, "letter_grade": letter,
        "status": status})


# ── provisioning + governance ────────────────────────────────────────────────
def test_c3_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c3_declares_aggregation_capability():
    pkg = build_college_manifest()["package"]
    assert "cross_record_aggregation" in pkg["requires_capabilities"]
    assert "grade_management" in pkg["provides_capabilities"]
    assert "transcripts" in pkg["provides_capabilities"]


@pytest.mark.django_db
def test_c3_install_provisions_grades_stack(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C3_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["compute_course_score", "grade_points_lookup", "compute_term_gpa", "compute_cgpa",
               "student_academic_standing", "compute_degree_progress"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    assert Dashboard.objects.filter(workspace_id=ws, slug="academic_performance_dashboard").exists()
    from apps.analytics.models import KPIDefinition
    assert KPIDefinition.objects.filter(workspace_id=ws, code="average_cgpa").exists()


@pytest.mark.django_db
def test_c3_gpa_is_pure_manifest_no_native_code(template):
    """The GPA/CGPA workflows carry ONLY action_aggregate measure/compute/target config — the
    calculation is the Core Aggregation Framework (CG-2), not any College code."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.workflows.models import WorkflowStep
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="compute_cgpa")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id,
                                    step_type="action_aggregate")
    assert set(step.config) >= {"measures", "computes", "target"}
    # the executor that runs it is the shared Core capability, not a College module
    from apps.workflows.executors import REGISTRY
    assert REGISTRY["action_aggregate"].__module__ == "apps.workflows.executors"


@pytest.mark.django_db
def test_c3_grade_approval_and_transcript_provisioned(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="grade_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="official_transcript").exists()


# ── the credit-weighted aggregates (the heart of C3) ─────────────────────────
@pytest.mark.django_db
def test_c3_term_gpa_credit_weighted(template, django_capture_on_commit_callbacks):
    """Term GPA = Σ(grade_points×credit_hours)/Σ(credit_hours) over published results — via
    action_aggregate, persisted to the semester_result."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=4.0)   # qp 12
    _result(ws, member, base, credit_hours=3, grade_points=3.0)   # qp 9   → Σqp 21 / Σcr 6 = 3.5
    with django_capture_on_commit_callbacks(execute=True):
        sr = _rec(ws, member, "semester_result", {"student": str(base["student"]["id"]),
                  "term": str(base["term"]["id"]), "program": str(base["program"]["id"]),
                  "status": "draft"})
    ref = _retrieve(ws, member, "semester_result", sr["id"])
    assert float(ref["term_gpa"]) == pytest.approx(3.5)
    assert float(ref["term_credits"]) == 6 and float(ref["term_quality_points"]) == 21


@pytest.mark.django_db
def test_c3_cgpa_and_deans_list_standing(template, django_capture_on_commit_callbacks):
    """CGPA over all published results; writing cgpa fires field_changed(cgpa) → the standing
    workflow sets Dean's List (≥3.5). Both aggregate + standing are pure manifest."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=4.0)   # qp 12
    _result(ws, member, base, credit_hours=3, grade_points=3.6)   # qp 10.8 → Σ22.8/6 = 3.8
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws, member, "student_academic_record",
                   {"student": str(base["student"]["id"]),
                    "program": str(base["program"]["id"]), "status": "active"})
    ref = _retrieve(ws, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(3.8)
    assert float(ref["credits_earned"]) == 6
    assert ref["academic_standing"] == "deans_list"


@pytest.mark.django_db
def test_c3_probation_standing(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=1.5, letter="D")   # CGPA 1.5 → probation
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws, member, "student_academic_record",
                   {"student": str(base["student"]["id"]),
                    "program": str(base["program"]["id"]), "status": "active"})
    ref = _retrieve(ws, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(1.5)
    assert ref["academic_standing"] == "probation"


@pytest.mark.django_db
def test_c3_repeat_course_superseded_excluded_from_gpa(
        template, django_capture_on_commit_callbacks):
    """Repeat policy: a superseded earlier attempt is NOT summed — only the latest published one."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=0.0, letter="F", status="superseded")
    _result(ws, member, base, credit_hours=3, grade_points=4.0, letter="A", status="published")
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws, member, "student_academic_record",
                   {"student": str(base["student"]["id"]),
                    "program": str(base["program"]["id"]), "status": "active"})
    ref = _retrieve(ws, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(4.0)   # only the retake counts
    assert float(ref["credits_earned"]) == 3


@pytest.mark.django_db
def test_c3_degree_progress(template, django_capture_on_commit_callbacks):
    """Degree audit: Σ published credits vs the program requirement (read as a single-row measure)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member, total_credits_required=120)
    _result(ws, member, base, credit_hours=12, grade_points=3.0)
    _result(ws, member, base, credit_hours=18, grade_points=3.0)   # 30 of 120 = 25%
    with django_capture_on_commit_callbacks(execute=True):
        dp = _rec(ws, member, "degree_progress", {"student": str(base["student"]["id"]),
                  "program": str(base["program"]["id"]), "status": "in_progress"})
    ref = _retrieve(ws, member, "degree_progress", dp["id"])
    assert float(ref["credits_completed"]) == 30 and float(ref["credits_required"]) == 120
    assert float(ref["progress_percent"]) == pytest.approx(25.0)


@pytest.mark.django_db
def test_c3_course_score_from_grade_book(template, django_capture_on_commit_callbacks):
    """Grade book: course_result.score = Σ(score×weight)/Σ(weight) over published assessment
    results — the reusable weighted-average pattern (action_aggregate)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _c3_base(ws, member)
    course = _rec(ws, member, "course", {"name": "Algorithms", "code": "CS201", "credit_hours": 3})
    section = _rec(ws, member, "course_section", {"course": str(course["id"]),
                   "term": str(base["term"]["id"]), "capacity": 30, "status": "open"})
    a1 = _rec(ws, member, "assessment", {"name": "Midterm", "course_section": str(section["id"]),
              "assessment_type": "midterm", "weight": 40, "max_score": 100, "status": "graded"})
    a2 = _rec(ws, member, "assessment", {"name": "Final", "course_section": str(section["id"]),
              "assessment_type": "final", "weight": 60, "max_score": 100, "status": "graded"})
    sid = str(base["student"]["id"])
    _rec(ws, member, "assessment_result", {"student": sid, "assessment": str(a1["id"]),
         "course_section": str(section["id"]), "score": 80, "weight": 40, "status": "published"})
    _rec(ws, member, "assessment_result", {"student": sid, "assessment": str(a2["id"]),
         "course_section": str(section["id"]), "score": 90, "weight": 60, "status": "published"})
    with django_capture_on_commit_callbacks(execute=True):
        cr = _rec(ws, member, "course_result", {"student": sid, "program": str(base["program"]["id"]),
                  "term": str(base["term"]["id"]), "course": str(course["id"]),
                  "course_section": str(section["id"]), "credit_hours": 3, "status": "draft"})
    ref = _retrieve(ws, member, "course_result", cr["id"])
    assert float(ref["score"]) == pytest.approx(86.0)   # (80·40 + 90·60)/100


@pytest.mark.django_db
def test_c3_grade_points_lookup_from_scale(template, django_capture_on_commit_callbacks):
    """Entering a letter grade resolves grade_points from the grade_scale via action_aggregate;
    quality_points (grade_points×credit_hours) then recomputes as a formula field."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    _grade_scale(ws, member)
    base = _c3_base(ws, member)
    course = _rec(ws, member, "course", {"name": "DB", "code": "CS301", "credit_hours": 4})
    cr = _rec(ws, member, "course_result", {"student": str(base["student"]["id"]),
              "program": str(base["program"]["id"]), "term": str(base["term"]["id"]),
              "course": str(course["id"]), "credit_hours": 4, "status": "draft"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "course_result", cr["id"], {"letter_grade": "A"})
    ref = _retrieve(ws, member, "course_result", cr["id"])
    assert float(ref["grade_points"]) == pytest.approx(4.0)
    assert float(ref["quality_points"]) == pytest.approx(16.0)   # 4.0 × 4 credit hours


@pytest.mark.django_db
def test_c3_workspace_isolation_of_gpa(template, django_capture_on_commit_callbacks):
    """A student's GPA never sums another workspace's results (RLS + workspace-scoped aggregation)."""
    member = system_member(None)
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    for ws in (ws_a, ws_b):
        sol.install(template_id=seed_college_template().id, workspace_id=ws, installed_by=None)
    base_a = _c3_base(ws_a, member)
    _result(ws_a, member, base_a, credit_hours=3, grade_points=4.0)
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws_a, member, "student_academic_record",
                   {"student": str(base_a["student"]["id"]),
                    "program": str(base_a["program"]["id"]), "status": "active"})
    ref = _retrieve(ws_a, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(4.0)
    # ws_b has no results → its academic record computes CGPA 0
    base_b = _c3_base(ws_b, member)
    with django_capture_on_commit_callbacks(execute=True):
        sar_b = _rec(ws_b, member, "student_academic_record",
                     {"student": str(base_b["student"]["id"]),
                      "program": str(base_b["program"]["id"]), "status": "active"})
    ref_b = _retrieve(ws_b, member, "student_academic_record", sar_b["id"])
    assert float(ref_b["cgpa"]) == 0


# ══ C4 — Faculty & Academic Advising ════════════════════════════════════════════
# Faculty PROFILE = the FROZEN C1 ``instructor`` (reused, not duplicated). C4 adds teaching/advising
# metadata + 2 more action_aggregate consumers (faculty workload, advisor caseload). Pure manifest.
C4_ENTITIES = ["teaching_assignment", "office_hour", "faculty_workload", "advisor_assignment",
               "advisor_caseload", "advising_session", "advising_note", "academic_hold",
               "override_request"]


def test_c4_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c4_declares_faculty_capability():
    pkg = build_college_manifest()["package"]
    assert "faculty_management" in pkg["provides_capabilities"]
    assert "academic_advising" in pkg["provides_capabilities"]


def test_c4_reuses_frozen_instructor_no_duplicate_faculty_entity():
    """Faculty profile/rank/employment-status = the C1 ``instructor`` (rank + status). C4 must NOT
    introduce a second faculty/employee entity — it looks up the frozen instructor."""
    from apps.college.blueprint import COLLEGE_OBJECTS
    assert "instructor" in COLLEGE_OBJECTS
    assert "faculty_employee" not in COLLEGE_OBJECTS and "faculty_member" not in COLLEGE_OBJECTS
    ta = COLLEGE_OBJECTS["teaching_assignment"]["fields"]
    assert any(f["slug"] == "instructor" and f.get("config", {}).get("target_entity_slug")
               == "instructor" for f in ta)


@pytest.mark.django_db
def test_c4_install_provisions_faculty_advising(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C4_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["compute_faculty_workload", "compute_advisor_caseload", "advisor_assigned",
               "academic_hold_placed", "override_submitted"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.analytics.models import KPIDefinition
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="override_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="faculty_profile").exists()
    for dash in ["faculty_dashboard", "advisor_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    assert KPIDefinition.objects.filter(workspace_id=ws, code="average_teaching_load").exists()


@pytest.mark.django_db
def test_c4_workload_is_pure_manifest_no_native_code(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.workflows.models import WorkflowStep
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="compute_faculty_workload")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id,
                                    step_type="action_aggregate")
    assert set(step.config) >= {"measures", "target"}
    from apps.workflows.executors import REGISTRY
    assert REGISTRY["action_aggregate"].__module__ == "apps.workflows.executors"


@pytest.mark.django_db
def test_c4_faculty_workload_aggregates(template, django_capture_on_commit_callbacks):
    """Teaching load = Σ(load_hours) + count(sections) over active teaching assignments — via
    action_aggregate, persisted to the faculty_workload record."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester",
                                     "status": "active"})
    instr = _rec(ws, member, "instructor", {"employee_no": "F001", "name": "Dr Ada",
                                            "rank": "professor", "status": "active"})
    for cr in range(2):
        course = _rec(ws, member, "course", {"name": f"C{cr}", "code": f"C{cr}", "credit_hours": 3})
        section = _rec(ws, member, "course_section", {"course": str(course["id"]),
                       "term": str(term["id"]), "capacity": 30, "status": "open"})
        _rec(ws, member, "teaching_assignment", {"instructor": str(instr["id"]),
             "course_section": str(section["id"]), "term": str(term["id"]),
             "role": "primary", "load_hours": 3, "status": "active"})
    with django_capture_on_commit_callbacks(execute=True):
        wl = _rec(ws, member, "faculty_workload", {"instructor": str(instr["id"]),
                  "term": str(term["id"]), "status": "draft"})
    ref = _retrieve(ws, member, "faculty_workload", wl["id"])
    assert float(ref["total_load_hours"]) == 6 and int(ref["section_count"]) == 2


@pytest.mark.django_db
def test_c4_advisor_caseload_aggregates(template, django_capture_on_commit_callbacks):
    """Advisor caseload = count(active advisor assignments) — via action_aggregate."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    advisor = _rec(ws, member, "instructor", {"employee_no": "A001", "name": "Dr Bo",
                                              "rank": "associate_professor", "status": "active"})
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "status": "active"})
    for i in range(3):
        st = _rec(ws, member, "student", {"first_name": f"S{i}", "program": str(prog["id"]),
                                          "status": "enrolled"})
        _rec(ws, member, "advisor_assignment", {"advisor": str(advisor["id"]),
             "student": str(st["id"]), "program": str(prog["id"]), "status": "active"})
    # an ended assignment must NOT count
    st_end = _rec(ws, member, "student", {"first_name": "Old", "program": str(prog["id"]),
                                          "status": "enrolled"})
    _rec(ws, member, "advisor_assignment", {"advisor": str(advisor["id"]),
         "student": str(st_end["id"]), "program": str(prog["id"]), "status": "ended"})
    with django_capture_on_commit_callbacks(execute=True):
        cl = _rec(ws, member, "advisor_caseload", {"advisor": str(advisor["id"]),
                  "status": "active"})
    ref = _retrieve(ws, member, "advisor_caseload", cl["id"])
    assert int(ref["active_advisees"]) == 3   # only the active assignments


# ══ C5 — Finance & Financial Aid (pure manifest consumer of the Core financial platform) ═════════
# EVERY money movement reuses a Core engine via a workflow step; College has ZERO accounting code.
C5_ENTITIES = ["tuition_category", "tuition_structure", "tuition_charge", "tuition_adjustment",
               "student_account", "student_payment", "aid_program", "aid_award", "aid_renewal",
               "sponsorship", "student_loan", "payment_plan", "payment_agreement", "financial_hold"]


def test_c5_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c5_declares_finance_capabilities():
    pkg = build_college_manifest()["package"]
    for cap in ("student_finance", "financial_aid", "tuition_management"):
        assert cap in pkg["provides_capabilities"], cap
    # money movement reuses Core: the package REQUIRES the accounting + documents capabilities
    assert "accounting" in pkg["requires_capabilities"]
    assert "documents" in pkg["requires_capabilities"]


def test_c5_defines_no_native_accounting():
    """College ships NO finance models/services — all posting is Core workflow steps. Prove the
    finance workflows carry only Core action_* engine steps, and College has no models module."""
    m = build_college_manifest()
    fin_steps = {s["step_type"] for w in m["workflows"] for s in w["steps"]
                 if s["step_type"].startswith(("action_post_journal", "action_apply_credit",
                                               "action_issue_refund", "action_create_installment"))}
    assert fin_steps <= {"action_post_journal", "action_apply_credit", "action_issue_refund",
                         "action_create_installment_plan"}
    # the College app registers ZERO Django models (pure manifest package — no native ledger/logic)
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("college").get_models()) == []


@pytest.mark.django_db
def test_c5_install_provisions_finance(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C5_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["tuition_charge_posting", "student_payment_posting", "aid_award_apply",
               "payment_plan_create", "financial_hold_placed", "graduation_finance_check"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.analytics.models import KPIDefinition
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    for proc in ["aid_approval", "loan_approval", "tuition_adjustment_approval"]:
        assert ApprovalProcess.objects.filter(workspace_id=ws, slug=proc).exists(), proc
    for doc in ["fee_statement", "tuition_invoice", "financial_aid_letter", "receipt"]:
        assert DocumentTemplate.objects.filter(workspace_id=ws, slug=doc).exists(), doc
    for role in ["bursar", "financial_aid_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="finance_dashboard").exists()
    assert KPIDefinition.objects.filter(workspace_id=ws, code="tuition_revenue").exists()


@pytest.mark.django_db
def test_c5_tuition_charge_posts_to_gl(template, django_capture_on_commit_callbacks):
    """Tuition charge → Core GL (Dr A/R 1100, Cr Revenue 4100) via action_post_journal. Zero
    College accounting — the JournalEntry is posted by GLBus."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "tuition_charge", {"amount": "5000.00", "status": "issued"})
    entries = JournalEntry.objects.filter(workspace_id=ws, source_module="college")
    assert entries.count() == 1
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entries.first().lines.all()}
    assert lines["1100"][0] == 5000 and lines["4100"][1] == 5000   # balanced receivable/revenue


@pytest.mark.django_db
def test_c5_student_payment_posts_to_gl(template, django_capture_on_commit_callbacks):
    """Student payment → Core GL (Dr Cash 1000, Cr A/R 1100)."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "student_payment", {"amount": "1200.00", "method": "bank"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="college").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1000"][0] == 1200 and lines["1100"][1] == 1200


@pytest.mark.django_db
def test_c5_aid_award_applies_credit_via_credit_engine(
        template, django_capture_on_commit_callbacks):
    """Approving an aid award fires the Core Credit Engine (a scholarship CreditNote → GL). Zero
    College credit/accounting logic."""
    from apps.credits.models import CreditNote
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Ada", "status": "enrolled"})
    award = _rec(ws, member, "aid_award", {"student": str(student["id"]), "aid_type": "scholarship",
                 "amount": "2000.00", "status": "requested"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "aid_award", award["id"], {"status": "approved"})
    note = CreditNote.objects.filter(workspace_id=ws, kind="scholarship").first()
    assert note is not None and note.amount == 2000


@pytest.mark.django_db
def test_c5_payment_plan_builds_installments_via_collections(
        template, django_capture_on_commit_callbacks):
    """Approving a payment plan fires the Core Collections Engine (plan + due schedule). Zero
    College collections logic."""
    from apps.collections_engine.models import Installment, InstallmentPlan
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Bo", "status": "enrolled"})
    plan = _rec(ws, member, "payment_plan", {"student": str(student["id"]),
                "total_amount": "3000.00", "num_installments": 3, "frequency": "monthly",
                "start_date": "2026-09-01", "status": "draft"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "payment_plan", plan["id"], {"status": "approved"})
    ip = InstallmentPlan.objects.filter(workspace_id=ws).first()
    assert ip is not None and ip.num_installments == 3
    assert Installment.objects.filter(workspace_id=ws, plan_id=ip.id).count() == 3


@pytest.mark.django_db
def test_c5_financial_hold_blocks_registration_via_frozen_c2(
        template, django_capture_on_commit_callbacks):
    """A financial hold REUSES the frozen C2 registration_hold + eligibility guard — it creates a
    registration_hold(financial), so a subsequent registration is waitlisted by the UNCHANGED C2
    guard. No duplicated hold/blocking logic."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _c2_setup(ws, member, capacity=10, max_credits=30)
    # place a financial hold on the student → creates an active registration_hold via the workflow
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "financial_hold", {"student": str(ctx["student"]["id"]),
             "reason": "Unpaid tuition", "status": "active"})
    # the frozen C2 guard now waitlists any registration for this student (proves the reused hold)
    status = _register(ws, member, ctx, django_capture_on_commit_callbacks)
    assert status == "waitlisted"


# ══ C6 — Campus Operations (pure manifest; reuses the frozen School campus-ops architecture) ══════
C6_ENTITIES = ["campus_charge", "library_book", "book_loan", "residence_room", "room_allocation",
               "transport_route", "transport_subscription", "medical_profile", "medical_visit",
               "medical_alert", "health_screening", "counselling_referral", "counselling_session",
               "student_club", "club_membership", "sport", "competition", "award",
               "student_activity", "visitor_log", "gate_pass", "incident_report", "welfare_case",
               "lost_and_found", "meal_plan", "id_card_request"]


def test_c6_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c6_declares_campus_capabilities():
    pkg = build_college_manifest()["package"]
    for cap in ("campus_operations", "library_management", "residence_life", "student_wellbeing"):
        assert cap in pkg["provides_capabilities"], cap


def test_c6_charges_reuse_core_no_native_accounting():
    """Charge-bearing campus services post via the Core GL step only — no College accounting."""
    m = build_college_manifest()
    charge_wf = next(w for w in m["workflows"] if w["slug"] == "campus_charge_posting")
    steps = {s["step_type"] for s in charge_wf["steps"]}
    assert steps <= {"action_post_journal", "action_generate_document"}   # Core engines only
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("college").get_models()) == []     # still zero native models


@pytest.mark.django_db
def test_c6_install_provisions_campus_ops(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C6_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["campus_charge_posting", "book_overdue_notice", "medical_alert_raised",
               "counselling_referral_created", "award_granted", "welfare_case_opened",
               "gate_pass_approved", "id_card_issued"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    from apps.portal.models import PortalEntityGrant
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="gate_pass_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="id_card").exists()
    for role in ["campus_services_officer", "campus_health_officer", "activities_coordinator",
                 "security_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["campus_services_dashboard", "health_wellbeing_dashboard",
                 "campus_security_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    # Portal engine reused — student-facing campus services exposed
    assert PortalEntityGrant.objects.filter(workspace_id=ws, entity_slug="book_loan").exists()


@pytest.mark.django_db
def test_c6_campus_charge_posts_to_gl_reusing_c5(template, django_capture_on_commit_callbacks):
    """A charge-bearing campus service (library fine / residence / meal) reuses the C5 financial
    platform: campus_charge → Core GL (Dr A/R 1100, Cr Revenue 4100). Zero College accounting."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "campus_charge", {"service_type": "library_fine", "amount": "25.00",
                                           "status": "issued"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="college").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 25 and lines["4100"][1] == 25


@pytest.mark.django_db
def test_c6_award_grant_fires_notification_workflow(template, django_capture_on_commit_callbacks):
    """Award granted → the reused School award_granted pattern fires (notification + certificate).
    Proves the campus-ops workflow runs end-to-end via the Core workflow engine."""
    from apps.workflows.models import WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Ada", "status": "enrolled"})
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "award", {"student": str(student["id"]), "award_name": "Dean's Medal"})
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="award_granted")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists()


# ══ C7 — Research (OVERLAY on the frozen Projects platform; NEVER duplicates PM) ═════════════════
C7_ENTITIES = ["research_center", "research_group", "research_project", "research_team_member",
               "research_student", "funding_agency", "research_proposal", "ethics_approval",
               "grant", "grant_application", "journal", "conference", "publication", "patent",
               "intellectual_property", "thesis", "research_contract"]

# The Projects platform is the SINGLE owner of these — Research must define NONE of them.
_PM_EXECUTION_ENTITIES = {"project", "task", "milestone", "deliverable", "task_dependency",
                          "dependency", "sprint", "timesheet", "expense", "risk", "issue",
                          "change_request", "quality_review", "research_task", "research_milestone",
                          "research_deliverable", "research_budget", "research_timesheet",
                          "research_dependency", "research_gantt", "research_resource_allocation"}


def test_c7_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c7_is_pure_overlay_no_pm_duplication():
    """BINDING boundary rule: Research defines ZERO project-management execution entities; a research
    project REFERENCES the Projects ``project`` via lookup. The Projects package stays the single
    source of truth for all PM (tasks/milestones/deliverables/budget/EVM/gantt/resources/timesheets)."""
    from apps.college.blueprint import COLLEGE_OBJECTS
    assert _PM_EXECUTION_ENTITIES.isdisjoint(COLLEGE_OBJECTS), \
        "Research must not duplicate Projects PM entities"
    proj_lk = next(f for f in COLLEGE_OBJECTS["research_project"]["fields"] if f["slug"] == "project")
    assert proj_lk.get("config", {}).get("target_entity_slug") == "project"   # → Projects package
    pkg = build_college_manifest()["package"]
    assert any(p["slug"] == "projects" for p in pkg["optional_packages"])     # declared dependency
    assert "research_management" in pkg["provides_capabilities"]


@pytest.mark.django_db
def test_c7_install_provisions_research(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C7_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["research_proposal_approved", "ethics_approved", "grant_awarded",
               "publication_published", "patent_granted", "thesis_defended"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.analytics.models import KPIDefinition
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    for proc in ["proposal_approval", "ethics_review", "grant_approval"]:
        assert ApprovalProcess.objects.filter(workspace_id=ws, slug=proc).exists(), proc
    for doc in ["grant_award_letter", "ethics_certificate", "thesis_certificate"]:
        assert DocumentTemplate.objects.filter(workspace_id=ws, slug=doc).exists(), doc
    for role in ["research_director", "principal_investigator", "grants_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="research_dashboard").exists()
    assert KPIDefinition.objects.filter(workspace_id=ws, code="total_grant_funding").exists()


@pytest.mark.django_db
def test_c7_grant_award_posts_funding_to_gl(template, django_capture_on_commit_callbacks):
    """Grant awarded → the C5 financial platform posts funding to the Core GL (Dr A/R 1100 from the
    agency, Cr Grant Revenue 4100). Grant budget/expenses stay on the Projects project — College
    posts only the funding-in, with zero package accounting."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    grant = _rec(ws, member, "grant", {"title": "NSF Grant", "award_amount": "100000.00",
                                       "status": "applied"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "grant", grant["id"], {"status": "awarded"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="college").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 100000 and lines["4100"][1] == 100000


@pytest.mark.django_db
def test_c7_research_project_links_projects_project(template):
    """A research_project stores a reference to a Projects ``project`` (the overlay linkage) — the
    field is a lookup to the external Projects entity; the record is created with that reference."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    proj_ref = str(uuid.uuid4())   # id of a Projects project (Projects installed separately)
    rp = _rec(ws, member, "research_project", {"title": "Quantum Study", "project": proj_ref,
              "research_type": "basic", "status": "active"})
    ref = _retrieve(ws, member, "research_project", rp["id"])
    assert str(ref["project"]) == proj_ref   # research overlay references the Projects project


# ══ C8 — Portal, Reporting & Executive Analytics (pure config over frozen platforms) ══════════════
C8_ENTITIES = ["accreditation_body", "accreditation", "compliance_requirement", "compliance_record"]


def test_c8_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c8_declares_analytics_capabilities():
    pkg = build_college_manifest()["package"]
    for cap in ("executive_analytics", "accreditation_management", "compliance_management",
                "parent_portal"):
        assert cap in pkg["provides_capabilities"], cap


def test_c8_is_pure_config_no_native_engine():
    """C8 is presentation/config over the frozen Reporting/Analytics/Dashboard/Portal platforms —
    zero native code/models. Prove the executive scorecards are Dashboard-runtime widgets over KPIs
    and College still registers no Django models."""
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("college").get_models()) == []
    m = build_college_manifest()
    scorecard = next(d for d in m["dashboards"] if d["slug"] == "executive_scorecard")
    assert {w["widget_type"] for w in scorecard["widgets"]} <= {"metric_card", "report"}  # runtime widgets


@pytest.mark.django_db
def test_c8_install_provisions_executive_layer(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in C8_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    from apps.analytics.models import KPIDefinition
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    from apps.portal.models import PortalEntityGrant
    for dash in ["executive_scorecard", "provost_dashboard", "cfo_dashboard", "risk_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    for kpi in ["total_students", "total_faculty", "accredited_programs",
                "overdue_compliance_items"]:
        assert KPIDefinition.objects.filter(workspace_id=ws, code=kpi).exists(), kpi
    for role in ["president", "provost", "compliance_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="compliance_review").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="accreditation_certificate").exists()
    # parent portal reuses the Portal engine (portal_type="parent")
    assert PortalEntityGrant.objects.filter(workspace_id=ws, entity_slug="course_result",
                                            portal_type="parent").exists()


@pytest.mark.django_db
def test_c8_executive_kpi_evaluates_via_analytics(template):
    """An executive KPI evaluates through the FROZEN Analytics engine (KPIService) — no new
    analytics engine."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for nm in ("A", "B", "C"):
        _rec(ws, member, "student", {"first_name": nm, "status": "enrolled"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="total_students")
    result = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert int(float(result["value"])) == 3


@pytest.mark.django_db
def test_c8_executive_role_home_routes(template):
    """President role auto-opens the executive scorecard via the FROZEN DG-5 role-home runtime."""
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    president = Role.objects.get(workspace_id=ws, slug="president")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(president.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "executive_scorecard"


# ══ C9 — Enterprise hardening (additive data-integrity rules + SLA; School Phase 1.8 pattern) ══════
def test_c9_manifest_validates_clean():
    assert validate_solution_manifest(build_college_manifest()) == []


def test_c9_is_additive_only_no_frozen_change():
    """C9 adds ONLY the new `rules` + `sla_policies` sections and reuses the generic Rules/SLA
    engines — every rule is a block_save guard (no new validation framework); College still native-free."""
    m = build_college_manifest()
    assert m["rules"] and m["sla_policies"]
    assert all(a["type"] == "block_save" for r in m["rules"] for a in r["actions"])  # generic engine
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("college").get_models()) == []


@pytest.mark.django_db
def test_c9_install_provisions_rules_and_sla(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.rules.models import BusinessRule
    from apps.sla.models import SLAPolicy
    # financial-integrity guards on the money fields that post to GL/Credits/Collections
    assert BusinessRule.objects.filter(
        workspace_id=ws, slug="validate_tuition_charge_amount_before_create").exists()
    assert BusinessRule.objects.filter(
        workspace_id=ws, slug="validate_grant_award_amount_before_create").exists()
    # academic-integrity guard
    assert BusinessRule.objects.filter(
        workspace_id=ws, slug="validate_course_result_grade_points_before_create").exists()
    # SLA response policies
    for pol in ["welfare_case_response", "incident_response", "ethics_review_turnaround"]:
        assert SLAPolicy.objects.filter(workspace_id=ws, slug=pol).exists(), pol


@pytest.mark.django_db
def test_c9_validation_rule_blocks_negative_money(template):
    """A negative tuition charge is rejected by the Core Rules engine (block_save) — protects the
    reused GL posting path from an invalid journal. Valid amounts still save."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "tuition_charge", {"amount": "-100.00", "status": "draft"})
    ok = _rec(ws, member, "tuition_charge", {"amount": "500.00", "status": "draft"})  # valid saves
    assert ok["id"]


@pytest.mark.django_db
def test_c9_validation_rule_blocks_out_of_range_grade(template):
    """Grade points > 4.0 are rejected — protects the CG-2 GPA calculation from corrupt input."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "course_result", {"credit_hours": 3, "grade_points": "5.0",
                                           "status": "draft"})
