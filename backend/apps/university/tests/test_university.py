"""
University package — Phase U1 (Academic Core + multi-college hierarchy) certification.

The 3rd education package. Pure manifest: every assertion is about manifest provisioning + reuse of
ERP Core engines (metadata/workflow/RBAC/reporting/analytics/dashboards) — zero native code.
Validates the optimized architecture (0 University-only master entities; multi-college hierarchy =
metadata on `faculty`) + independence + coexistence with the frozen School/College packages.
"""
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.reporting.models import Dashboard, Report
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member
from apps.solution_templates.models import InstalledSolution
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.university.blueprint import build_university_manifest, seed_university_template
from apps.workflows.models import WorkflowDefinition

U1_ENTITIES = [
    "campus", "academic_year", "term", "academic_calendar_event", "faculty", "department",
    "program", "specialization", "course", "prerequisite", "instructor", "course_section",
    "curriculum", "curriculum_course", "student", "program_enrollment",
]


@pytest.fixture
def template(db):
    return seed_university_template()


def _rec(ws, member, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=member, entity=entity, data=data)


# ── manifest + provisioning ──────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_package_is_independent_third_education_package():
    pkg = build_university_manifest()["package"]
    assert pkg["slug"] == "university" and pkg["version"] == "1.0.0"
    assert pkg["requires_packages"] == []                    # installs standalone on Core
    # optional only — hr (instructors↔employees) + projects (U7 research_project overlay)
    assert {p["slug"] for p in pkg["optional_packages"]} == {"hr", "projects"}
    assert "multi_college" in pkg["provides_capabilities"]


def test_u1_has_zero_university_only_master_entities():
    """Optimization invariant: University adds NO new master entity — the academic spine is the
    (future) Academic-Base pattern, and every University concept is metadata on it."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U1_ENTITIES) <= set(UNIVERSITY_OBJECTS)     # the 16 spine masters are all present
    # multi-college hierarchy = metadata on faculty (self-ref parent + org_level), NOT a new entity
    fac = {f["slug"] for f in UNIVERSITY_OBJECTS["faculty"]["fields"]}
    assert {"parent", "org_level"} <= fac
    assert "college" not in UNIVERSITY_OBJECTS and "school" not in UNIVERSITY_OBJECTS
    # double/joint/ECTS = program metadata; exchange/international = student metadata
    prog = {f["slug"] for f in UNIVERSITY_OBJECTS["program"]["fields"]}
    assert {"program_type", "partner_program", "credit_system"} <= prog
    stu = {f["slug"] for f in UNIVERSITY_OBJECTS["student"]["fields"]}
    assert {"student_type", "visa_status", "home_institution"} <= stu


@pytest.mark.django_db
def test_install_provisions_academic_core(template):
    ws = uuid.uuid4()
    installed = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert installed.installed_version == "1.0.0"
    for slug in U1_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for role in ["university_administrator", "registrar", "dean", "department_head", "instructor"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["executive_dashboard", "registrar_dashboard", "academic_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    assert Report.objects.filter(workspace_id=ws, slug="enrollment_report").exists()
    assert Application.objects.filter(workspace_id=ws, slug="university").exists()
    assert WorkflowDefinition.objects.filter(
        workspace_id=ws, slug="program_enrollment_activated").exists()


@pytest.mark.django_db
def test_multi_college_hierarchy_is_metadata(template):
    """A College/School/Faculty tree is modelled by `faculty` rows at different org_levels with a
    self-referencing parent — zero new entities."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    college = _rec(ws, member, "faculty", {"name": "College of Engineering", "code": "COE",
                                           "org_level": "college"})
    fac = _rec(ws, member, "faculty", {"name": "Faculty of Mechanical Eng", "code": "FME",
                                       "org_level": "faculty", "parent": str(college["id"])})
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="faculty")
    ref = RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                        record_id=fac["id"])
    assert str(ref["parent"]) == str(college["id"]) and ref["org_level"] == "faculty"


# ── reuse: workflow, role dashboards (DG-5), analytics KPI ────────────────────
@pytest.mark.django_db
def test_program_enrollment_marks_student_enrolled(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "degree_type": "bachelor",
                                        "program_type": "single", "status": "active"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "student_type": "regular", "status": "applicant"})
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "program_enrollment",
             {"student": str(student["id"]), "program": str(prog["id"]), "status": "active"})
    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    refreshed = RecordService.retrieve_record(workspace_id=ws, member=member,
                                              entity=student_entity, record_id=student["id"])
    assert refreshed["status"] == "enrolled"


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
    _rec(ws, member, "student", {"first_name": "A", "student_type": "international",
                                 "status": "enrolled"})
    _rec(ws, member, "student", {"first_name": "B", "student_type": "regular", "status": "enrolled"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="international_students")
    result = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert int(float(result["value"])) == 1


# ── package lifecycle + coexistence with the frozen School/College packages ───
@pytest.mark.django_db
def test_university_coexists_with_college_in_separate_workspaces():
    """All three education packages are catalog-coexistent: each installs cleanly into its OWN
    workspace with no cross-workspace bleed (the real deployment model)."""
    from apps.college.blueprint import seed_college_template
    ws_uni, ws_col = uuid.uuid4(), uuid.uuid4()
    sol.install(template_id=seed_university_template().id, workspace_id=ws_uni, installed_by=None)
    sol.install(template_id=seed_college_template().id, workspace_id=ws_col, installed_by=None)
    assert EntityDefinition.objects.filter(workspace_id=ws_uni, slug="program").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws_col, slug="program").exists()
    # multi-college org_level exists on University's faculty, not College's frozen faculty
    uni_fac = EntityDefinition.objects.get(workspace_id=ws_uni, slug="faculty")
    from apps.metadata.models import FieldDefinition
    uni_fac_fields = set(FieldDefinition.objects.filter(
        workspace_id=ws_uni, entity_id=uni_fac.id).values_list("slug", flat=True))
    assert "org_level" in uni_fac_fields


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
    seed_university_template()
    seed_university_template()
    from apps.solution_templates.models import SolutionTemplate
    assert SolutionTemplate.objects.filter(slug="university").count() == 1


@pytest.mark.django_db
def test_nav_wires_academic_core(template):
    m = build_university_manifest()
    nav_targets = {item["target"] for grp in m["navigations"][0]["tree"] for item in grp["items"]}
    for slug in ["program", "course", "course_section", "student", "faculty"]:
        assert slug in nav_targets, slug
    assert set(U1_ENTITIES) <= set(m["applications"][0]["included_entity_slugs"])


# ══ U2 — Course Registration (mirrors College C2; Guard Framework reused; 0 University-only) ═══════
U2_ENTITIES = ["registration_period", "registration_hold", "registration", "waitlist_entry"]


def _u2_setup(ws, member, *, capacity=2, max_credits=30):
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "degree_type": "bachelor",
                                        "program_type": "single", "status": "active",
                                        "max_credits_per_term": max_credits})
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester", "status": "active"})
    course = _rec(ws, member, "course", {"name": "Intro CS", "code": "CS101", "credit_hours": 3})
    section = _rec(ws, member, "course_section", {"course": str(course["id"]),
                   "term": str(term["id"]), "capacity": capacity, "status": "open"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "student_type": "regular", "status": "enrolled"})
    return {"program": prog, "term": term, "course": course, "section": section, "student": student}


def _register(ws, member, ctx, on_commit, *, student=None, section=None, credits=3,
              enrollment_type="regular"):
    with on_commit(execute=True):
        reg = _rec(ws, member, "registration", {
            "student": str((student or ctx["student"])["id"]),
            "program": str(ctx["program"]["id"]), "course": str(ctx["course"]["id"]),
            "course_section": str((section or ctx["section"])["id"]),
            "term": str(ctx["term"]["id"]), "credit_hours": credits,
            "enrollment_type": enrollment_type, "status": "confirmed"})
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="registration")
    return RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                         record_id=reg["id"])["status"]


def test_u2_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u2_is_zero_university_only_entities():
    """U2 adds exactly the 4 College-C2 registration entities and NO University-only entity;
    exchange/visiting/cross-campus/inter-college/cross-listing are metadata on `registration`."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U2_ENTITIES) <= set(UNIVERSITY_OBJECTS)     # the 4 College-C2 registration entities
    reg = {f["slug"] for f in UNIVERSITY_OBJECTS["registration"]["fields"]}
    assert {"enrollment_type", "host_campus", "is_inter_college", "listed_as"} <= reg
    pkg = build_university_manifest()["package"]
    assert "cross_record_validation" in pkg["requires_capabilities"]   # Guard Framework
    assert pkg["requires_packages"] == []                              # still independent


@pytest.mark.django_db
def test_u2_install_provisions_registration(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U2_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(
        workspace_id=ws, slug="registration_eligibility").exists()
    assert Role.objects.filter(workspace_id=ws, slug="academic_advisor").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="registration_dashboard").exists()


@pytest.mark.django_db
def test_u2_guard_reused_unchanged(template):
    """The eligibility step is the Core Guard Framework with the SAME three guards as College C2 —
    no University-specific enforcement logic."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.workflows.models import WorkflowStep
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="registration_eligibility")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    assert {g["name"] for g in step.config["guards"]} == {"capacity", "credit_limit", "no_active_hold"}


@pytest.mark.django_db
def test_u2_registration_confirmed_within_limits(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _u2_setup(ws, member, capacity=2, max_credits=30)
    assert _register(ws, member, ctx, django_capture_on_commit_callbacks) == "confirmed"


@pytest.mark.django_db
def test_u2_guard_waitlists_when_section_full(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _u2_setup(ws, member, capacity=1, max_credits=30)
    assert _register(ws, member, ctx, django_capture_on_commit_callbacks) == "confirmed"
    other = _rec(ws, member, "student", {"first_name": "Bo", "program": str(ctx["program"]["id"]),
                                         "student_type": "regular", "status": "enrolled"})
    assert _register(ws, member, ctx, django_capture_on_commit_callbacks, student=other) == "waitlisted"


@pytest.mark.django_db
def test_u2_guard_waitlists_when_active_hold(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _u2_setup(ws, member, capacity=10, max_credits=30)
    _rec(ws, member, "registration_hold", {"student": str(ctx["student"]["id"]),
                                            "hold_type": "financial", "status": "active"})
    assert _register(ws, member, ctx, django_capture_on_commit_callbacks) == "waitlisted"


@pytest.mark.django_db
def test_u2_exchange_enrollment_is_metadata(template, django_capture_on_commit_callbacks):
    """An exchange registration is the SAME entity + a metadata enrollment_type — no parallel model,
    and the guard treats it identically."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _u2_setup(ws, member, capacity=5, max_credits=30)
    exch = _rec(ws, member, "student", {"first_name": "Kai", "program": str(ctx["program"]["id"]),
                                        "student_type": "exchange", "status": "enrolled"})
    status = _register(ws, member, ctx, django_capture_on_commit_callbacks, student=exch,
                       enrollment_type="exchange")
    assert status == "confirmed"


# ══ U3 — Grades / GPA / Transcript (mirrors College C3; CG-2 reused unchanged; 0 new entities) ═════
U3_ENTITIES = ["grade_scheme", "grade_scale", "assessment", "assessment_result", "course_result",
               "semester_result", "student_academic_record", "degree_progress", "transfer_credit",
               "graduation_application"]


def _retrieve(ws, member, slug, rid):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity, record_id=rid)


def _update(ws, member, slug, rid, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.update_record(workspace_id=ws, member=member, entity=entity,
                                       record_id=rid, data=data)


def _u3_base(ws, member):
    prog = _rec(ws, member, "program", {"name": "BSc CS", "code": "BSCS", "degree_type": "bachelor",
                                        "program_type": "single", "status": "active",
                                        "total_credits_required": 120})
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester", "status": "active"})
    student = _rec(ws, member, "student", {"first_name": "Ada", "program": str(prog["id"]),
                                           "student_type": "regular", "status": "enrolled"})
    return {"program": prog, "term": term, "student": student}


def _result(ws, member, base, *, credit_hours, grade_points, grade_mode="graded",
            status="published"):
    import uuid as _u
    code = f"C{_u.uuid4().hex[:6]}"
    course = _rec(ws, member, "course", {"name": code, "code": code, "credit_hours": credit_hours})
    return _rec(ws, member, "course_result", {
        "student": str(base["student"]["id"]), "program": str(base["program"]["id"]),
        "term": str(base["term"]["id"]), "course": str(course["id"]),
        "credit_hours": credit_hours, "grade_points": grade_points, "letter_grade": "A",
        "grade_mode": grade_mode, "status": status})


def test_u3_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u3_zero_new_university_only_entities():
    """U3 materializes exactly the 10 College-C3 grade-cluster entities; University differences
    (graduate/doctoral/pass-fail/honours/exchange) are metadata on them, not new entities."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U3_ENTITIES) <= set(UNIVERSITY_OBJECTS)
    cr = {f["slug"] for f in UNIVERSITY_OBJECTS["course_result"]["fields"]}
    assert "grade_mode" in cr                                    # pass/fail = metadata
    sar = {f["slug"] for f in UNIVERSITY_OBJECTS["student_academic_record"]["fields"]}
    assert "honours" in sar                                      # honours classification = metadata
    gs = {f["slug"] for f in UNIVERSITY_OBJECTS["grade_scheme"]["fields"]}
    assert "scheme_level" in gs                                  # graduate/doctoral = data
    pkg = build_university_manifest()["package"]
    assert "cross_record_aggregation" in pkg["requires_capabilities"]   # CG-2
    assert pkg["requires_packages"] == []                              # still independent


@pytest.mark.django_db
def test_u3_install_provisions_grades_stack(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U3_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["compute_term_gpa", "compute_cgpa", "student_academic_standing",
               "university_honours_classification", "compute_degree_progress"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="grade_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="official_transcript").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="academic_performance_dashboard").exists()


@pytest.mark.django_db
def test_u3_term_gpa_via_cg2(template, django_capture_on_commit_callbacks):
    """Term GPA = Σ(quality_points)/Σ(credit_hours) via action_aggregate (CG-2 unchanged)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _u3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=4.0)   # qp 12
    _result(ws, member, base, credit_hours=3, grade_points=3.0)   # qp 9 → 21/6 = 3.5
    with django_capture_on_commit_callbacks(execute=True):
        sr = _rec(ws, member, "semester_result", {"student": str(base["student"]["id"]),
                  "term": str(base["term"]["id"]), "program": str(base["program"]["id"]),
                  "status": "draft"})
    ref = _retrieve(ws, member, "semester_result", sr["id"])
    assert float(ref["term_gpa"]) == pytest.approx(3.5) and float(ref["term_credits"]) == 6


@pytest.mark.django_db
def test_u3_cgpa_standing_and_honours(template, django_capture_on_commit_callbacks):
    """CGPA (CG-2) fires BOTH the standing ladder and the University honours ladder via
    field_changed(cgpa)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _u3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=4.0)   # qp 12
    _result(ws, member, base, credit_hours=3, grade_points=3.6)   # qp 10.8 → 22.8/6 = 3.8
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws, member, "student_academic_record",
                   {"student": str(base["student"]["id"]),
                    "program": str(base["program"]["id"]), "status": "active"})
    ref = _retrieve(ws, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(3.8)
    assert ref["academic_standing"] == "deans_list"      # >= 3.5
    assert ref["honours"] == "first_class"               # >= 3.7 (University honours ladder)


@pytest.mark.django_db
def test_u3_pass_fail_excluded_from_gpa_but_counts_credits(
        template, django_capture_on_commit_callbacks):
    """University: a pass/fail research credit is EXCLUDED from GPA (grade_mode filter) but still
    counts toward earned credits / degree progress — all via CG-2 config, no engine change."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    base = _u3_base(ws, member)
    _result(ws, member, base, credit_hours=3, grade_points=4.0, grade_mode="graded")     # counts
    _result(ws, member, base, credit_hours=3, grade_points=0.0, grade_mode="pass_fail")  # excl. GPA
    with django_capture_on_commit_callbacks(execute=True):
        sar = _rec(ws, member, "student_academic_record",
                   {"student": str(base["student"]["id"]),
                    "program": str(base["program"]["id"]), "status": "active"})
    ref = _retrieve(ws, member, "student_academic_record", sar["id"])
    assert float(ref["cgpa"]) == pytest.approx(4.0)      # only the graded course → 12/3 = 4.0
    assert float(ref["credits_earned"]) == 3             # graded credits only in CGPA measure
    # degree progress counts ALL published credits (graded + pass/fail = 6)
    with django_capture_on_commit_callbacks(execute=True):
        dp = _rec(ws, member, "degree_progress", {"student": str(base["student"]["id"]),
                  "program": str(base["program"]["id"]), "status": "in_progress"})
    dref = _retrieve(ws, member, "degree_progress", dp["id"])
    assert float(dref["credits_completed"]) == 6         # pass/fail credits DO count toward the degree


# ══ U4 — Faculty · Advising · Graduate Supervision (mirrors College C4 + generic grad supervision) ══
U4_ENTITIES = ["teaching_assignment", "office_hour", "faculty_workload", "advisor_assignment",
               "advisor_caseload", "advising_session", "advising_note", "academic_hold",
               "override_request", "graduate_committee", "graduate_review"]

# Specialised committee/defense entities that the permanent University rule FORBIDS (must be
# represented by graduate_committee/graduate_review + committee_type/review_type).
_FORBIDDEN_GRAD_ENTITIES = {"thesis_committee", "dissertation_committee", "proposal_committee",
                            "viva_committee", "comprehensive_exam_committee", "annual_review",
                            "thesis_defense", "dissertation_defense", "viva"}


def test_u4_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u4_graduate_supervision_uses_only_generic_entities():
    """Permanent rule: the ONLY committee/review entities are graduate_committee + graduate_review;
    specialised committees/defenses are committee_type/review_type metadata; supervisor/co-supervisor/
    external-examiner are advisor_assignment metadata."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert {"graduate_committee", "graduate_review"} <= set(UNIVERSITY_OBJECTS)
    assert _FORBIDDEN_GRAD_ENTITIES.isdisjoint(UNIVERSITY_OBJECTS)   # none of the specialised entities
    gc = {f["slug"] for f in UNIVERSITY_OBJECTS["graduate_committee"]["fields"]}
    assert "committee_type" in gc
    gr = {f["slug"] for f in UNIVERSITY_OBJECTS["graduate_review"]["fields"]}
    assert "review_type" in gr
    aa = {f["slug"] for f in UNIVERSITY_OBJECTS["advisor_assignment"]["fields"]}
    assert {"advisor_role", "committee", "is_external"} <= aa   # supervisor/external = metadata


@pytest.mark.django_db
def test_u4_install_provisions_faculty_advising_graduate(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U4_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["compute_faculty_workload", "compute_advisor_caseload",
               "graduate_committee_approved", "graduate_review_completed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="graduate_committee_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="committee_appointment").exists()
    assert Role.objects.filter(workspace_id=ws, slug="graduate_school_officer").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="graduate_school_dashboard").exists()


@pytest.mark.django_db
def test_u4_faculty_workload_aggregates_via_cg2(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    term = _rec(ws, member, "term", {"name": "Fall 2026", "term_type": "semester", "status": "active"})
    instr = _rec(ws, member, "instructor", {"employee_no": "F001", "name": "Dr Ada",
                                            "rank": "professor", "status": "active"})
    for _ in range(2):
        course = _rec(ws, member, "course", {"name": "C", "code": f"C{uuid.uuid4().hex[:5]}",
                                             "credit_hours": 3})
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
def test_u4_graduate_committee_and_review_lifecycle(template, django_capture_on_commit_callbacks):
    """A PhD committee + a comprehensive-exam review are one graduate_committee + one graduate_review
    (committee_type/review_type), with a co-supervisor as advisor_assignment metadata."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    prog = _rec(ws, member, "program", {"name": "PhD CS", "code": "PHDCS",
                                        "degree_type": "doctorate", "status": "active"})
    student = _rec(ws, member, "student", {"first_name": "Kai", "program": str(prog["id"]),
                                           "student_type": "regular", "status": "enrolled"})
    chair = _rec(ws, member, "instructor", {"employee_no": "S001", "name": "Prof Bo",
                                            "rank": "professor", "status": "active"})
    committee = _rec(ws, member, "graduate_committee", {"student": str(student["id"]),
                     "program": str(prog["id"]), "committee_type": "dissertation",
                     "chair": str(chair["id"]), "status": "proposed"})
    # co-supervisor = advisor_assignment metadata (advisor_role), linked to the committee
    co = _rec(ws, member, "instructor", {"employee_no": "S002", "name": "Dr Co", "status": "active"})
    _rec(ws, member, "advisor_assignment", {"advisor": str(co["id"]), "student": str(student["id"]),
         "advisor_role": "co_supervisor", "committee": str(committee["id"]), "status": "active"})
    # a comprehensive-exam review event = graduate_review (review_type), not a specialised entity
    review = _rec(ws, member, "graduate_review", {"student": str(student["id"]),
                  "graduate_committee": str(committee["id"]), "review_type": "comprehensive",
                  "outcome": "pass", "status": "scheduled"})
    ref = _retrieve(ws, member, "graduate_review", review["id"])
    assert ref["review_type"] == "comprehensive"
    # the committee-approved workflow fires on approval
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "graduate_committee", committee["id"], {"status": "approved"})
    from apps.workflows.models import WorkflowRun
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="graduate_committee_approved")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists()


# ══ U5 — Finance & Financial Aid (mirrors College C5; consumes the Core Financial Platform) ═══════
U5_ENTITIES = ["tuition_category", "tuition_structure", "tuition_charge", "tuition_adjustment",
               "student_account", "student_payment", "aid_program", "aid_award", "aid_renewal",
               "sponsorship", "student_loan", "payment_plan", "payment_agreement", "financial_hold"]


def test_u5_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u5_finance_is_metadata_no_new_entities_no_native():
    """U5 = the 14 College-C5 finance entities; University differences (assistantship/fellowship/
    loan/sponsorship types, funding source) are metadata. Zero native accounting; University app has
    no models."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U5_ENTITIES) <= set(UNIVERSITY_OBJECTS)
    at = [f for f in UNIVERSITY_OBJECTS["aid_award"]["fields"] if f["slug"] == "aid_type"][0]
    assert "research_assistantship" in at["config"]["choices"]   # assistantship = metadata
    lt = {f["slug"] for f in UNIVERSITY_OBJECTS["student_loan"]["fields"]}
    assert "loan_type" in lt
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("university").get_models()) == []
    pkg = build_university_manifest()["package"]
    assert "accounting" in pkg["requires_capabilities"] and pkg["requires_packages"] == []


@pytest.mark.django_db
def test_u5_install_provisions_finance(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U5_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["tuition_charge_posting", "student_payment_posting", "aid_award_apply",
               "student_loan_disburse", "financial_hold_placed", "graduation_finance_check"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    for proc in ["aid_approval", "loan_approval", "tuition_adjustment_approval"]:
        assert ApprovalProcess.objects.filter(workspace_id=ws, slug=proc).exists(), proc
    for role in ["bursar", "financial_aid_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="finance_dashboard").exists()


@pytest.mark.django_db
def test_u5_tuition_charge_posts_to_gl(template, django_capture_on_commit_callbacks):
    """Tuition charge → Core GL (Dr A/R 1100, Cr Revenue 4100). Zero University accounting."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "tuition_charge", {"amount": "8000.00", "status": "issued"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="university").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 8000 and lines["4100"][1] == 8000


@pytest.mark.django_db
def test_u5_aid_award_applies_credit(template, django_capture_on_commit_callbacks):
    """Approving an aid award (incl. assistantships) fires the Core Credit Engine."""
    from apps.credits.models import CreditNote
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Ada", "student_type": "regular",
                                           "status": "enrolled"})
    award = _rec(ws, member, "aid_award", {"student": str(student["id"]),
                 "aid_type": "research_assistantship", "amount": "5000.00", "status": "requested"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "aid_award", award["id"], {"status": "approved"})
    note = CreditNote.objects.filter(workspace_id=ws, kind="scholarship").first()
    assert note is not None and note.amount == 5000


@pytest.mark.django_db
def test_u5_payment_plan_builds_installments(template, django_capture_on_commit_callbacks):
    from apps.collections_engine.models import Installment, InstallmentPlan
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Bo", "status": "enrolled"})
    plan = _rec(ws, member, "payment_plan", {"student": str(student["id"]),
                "total_amount": "9000.00", "num_installments": 3, "frequency": "monthly",
                "start_date": "2026-09-01", "status": "draft"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "payment_plan", plan["id"], {"status": "approved"})
    ip = InstallmentPlan.objects.filter(workspace_id=ws).first()
    assert ip is not None and ip.num_installments == 3
    assert Installment.objects.filter(workspace_id=ws, plan_id=ip.id).count() == 3


@pytest.mark.django_db
def test_u5_financial_hold_blocks_registration_via_frozen_u2(
        template, django_capture_on_commit_callbacks):
    """A financial hold REUSES the frozen U2 registration_hold + eligibility guard — a subsequent
    registration is waitlisted by the UNCHANGED U2 guard."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _u2_setup(ws, member, capacity=10, max_credits=30)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "financial_hold", {"student": str(ctx["student"]["id"]),
             "reason": "Unpaid tuition", "status": "active"})
    assert _register(ws, member, ctx, django_capture_on_commit_callbacks) == "waitlisted"


# ══ U6 — Campus Operations (mirrors College C6; charges reuse the Financial Platform) ═════════════
U6_ENTITIES = ["campus_charge", "library_book", "book_loan", "residence_room", "room_allocation",
               "transport_route", "transport_subscription", "access_permit", "medical_profile",
               "medical_visit", "medical_alert", "counselling_referral", "student_club", "sport",
               "competition", "award", "student_activity", "visitor_log", "gate_pass",
               "incident_report", "welfare_case", "lost_and_found", "meal_plan", "id_card_request"]


def test_u6_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u6_access_permit_is_generic_not_parking_specific():
    """The one new campus-ops object is the GENERIC access_permit (permit_type metadata), NOT a
    parking-specific entity — the graduate_committee/graduate_review generalization applied to
    permits. gate_pass (one-time event) and campus_charge (fee) stay distinct."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert "access_permit" in UNIVERSITY_OBJECTS
    assert "parking_permit" not in UNIVERSITY_OBJECTS
    pt = [f for f in UNIVERSITY_OBJECTS["access_permit"]["fields"] if f["slug"] == "permit_type"][0]
    for kind in ("parking", "lab_access", "residence_access"):
        assert kind in pt["config"]["choices"]
    # gate_pass and campus_charge remain separate concepts
    assert "gate_pass" in UNIVERSITY_OBJECTS and "campus_charge" in UNIVERSITY_OBJECTS


@pytest.mark.django_db
def test_u6_install_provisions_campus_ops(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U6_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["campus_charge_posting", "access_permit_issued", "medical_alert_raised",
               "award_granted", "welfare_case_opened", "id_card_issued"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="gate_pass_approval").exists()
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="id_card").exists()
    for role in ["campus_services_officer", "campus_health_officer", "activities_coordinator",
                 "security_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="campus_services_dashboard").exists()


@pytest.mark.django_db
def test_u6_campus_charge_posts_to_gl(template, django_capture_on_commit_callbacks):
    """A charge-bearing campus service (library fine / residence / meal / parking) reuses the
    Financial Platform: campus_charge → Core GL (Dr A/R 1100, Cr Revenue 4100)."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "campus_charge", {"service_type": "parking", "amount": "150.00",
                                           "status": "issued"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="university").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 150 and lines["4100"][1] == 150


@pytest.mark.django_db
def test_u6_access_permit_lifecycle_and_award_workflow(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Ada", "status": "enrolled"})
    # a parking permit is an access_permit with permit_type=parking
    permit = _rec(ws, member, "access_permit", {"student": str(student["id"]),
                  "permit_type": "parking", "resource_ref": "zone_a",
                  "reference_detail": "ABC-123", "status": "issued"})
    ref = _retrieve(ws, member, "access_permit", permit["id"])
    assert ref["permit_type"] == "parking"
    # award-granted workflow fires (reused School/College pattern)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "award", {"student": str(student["id"]), "award_name": "Dean's Medal"})
    from apps.workflows.models import WorkflowRun
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="award_granted")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists()


# ══ U7 — Research Administration (overlay on the frozen Projects platform) ═════════════════════════
U7_ENTITIES = ["research_center", "research_group", "research_project", "research_team_member",
               "funding_agency", "research_proposal", "ethics_approval", "grant",
               "grant_application", "journal", "conference", "publication", "patent",
               "intellectual_property", "research_contract"]

# Entities the permanent Research↔Projects + graduate-supervision rules FORBID in Research (owned by
# the Projects platform, or already U4 graduate supervision, or the deposited work = publication).
_FORBIDDEN_RESEARCH_ENTITIES = {
    # already U4 graduate supervision / deposited work = publication
    "thesis", "dissertation", "research_student", "thesis_defense", "dissertation_defense",
    "proposal_defense", "viva", "comprehensive_exam",
    # owned by the Projects platform — never duplicated inside Research
    "research_task", "research_milestone", "research_deliverable", "research_budget",
    "research_dependency", "research_gantt", "research_timesheet", "research_resource_allocation",
    "research_risk", "research_issue", "research_change_request",
}


def test_u7_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u7_is_exactly_15_research_entities_no_forbidden():
    """U7 = 15 scholarly entities. Thesis/research_student are REJECTED (U4 graduate_committee/
    graduate_review + publication represent them); NO Projects/PM entity is duplicated."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U7_ENTITIES) <= set(UNIVERSITY_OBJECTS)
    assert _FORBIDDEN_RESEARCH_ENTITIES.isdisjoint(UNIVERSITY_OBJECTS)


def test_u7_research_project_is_overlay_on_projects():
    """research_project is a thin OVERLAY that references the frozen Projects `project` — scholarly
    fields only, no schedule/budget/task fields."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    fields = {f["slug"]: f for f in UNIVERSITY_OBJECTS["research_project"]["fields"]}
    assert fields["project"]["config"]["target_entity_slug"] == "project"   # → Projects platform
    # no PM fields copied onto the overlay
    assert {"budget", "task", "milestone", "gantt", "timesheet"}.isdisjoint(fields)
    pkg = build_university_manifest()["package"]
    assert {"projects", "hr"} == {p["slug"] for p in pkg["optional_packages"]}
    assert "research_management" in pkg["provides_capabilities"]


def test_u7_graduate_work_represented_by_generic_entities():
    """The graduate research population + deposited work reuse existing entities: a research student =
    research_team_member(member_type) + advisor_assignment(supervisor); a thesis = publication."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    mt = [f for f in UNIVERSITY_OBJECTS["research_team_member"]["fields"]
          if f["slug"] == "member_type"][0]
    assert "graduate_research_student" in mt["config"]["choices"]
    pt = [f for f in UNIVERSITY_OBJECTS["publication"]["fields"]
          if f["slug"] == "publication_type"][0]
    assert {"thesis", "dissertation"} <= set(pt["config"]["choices"])


@pytest.mark.django_db
def test_u7_install_provisions_research(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U7_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["research_proposal_approved", "ethics_approved", "grant_awarded",
               "publication_published", "patent_granted", "research_contract_signed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    from apps.approvals.models import ApprovalProcess
    from apps.document_templates.models import DocumentTemplate
    for proc in ["research_proposal_approval", "ethics_approval_process"]:
        assert ApprovalProcess.objects.filter(workspace_id=ws, slug=proc).exists(), proc
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="grant_award_letter").exists()
    for role in ["research_director", "principal_investigator", "research_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="research_dashboard").exists()


@pytest.mark.django_db
def test_u7_grant_awarded_posts_to_gl(template, django_capture_on_commit_callbacks):
    """Grant funding reuses the Core Financial Platform: awarding a grant posts to GL
    (Dr A/R 1100, Cr Revenue 4100). Zero University accounting; budget/expenses stay on Projects."""
    from apps.ledger.models import JournalEntry
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    grant = _rec(ws, member, "grant", {"title": "NSF Discovery Grant",
                                       "award_amount": "100000.00", "status": "applied"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "grant", grant["id"], {"status": "awarded"})
    entry = JournalEntry.objects.filter(workspace_id=ws, source_module="university").first()
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 100000 and lines["4100"][1] == 100000


@pytest.mark.django_db
def test_u7_research_output_lifecycle(template, django_capture_on_commit_callbacks):
    """A publication + a research-team membership are pure scholarly records; the
    publication_published workflow fires on publish (reused Workflow/Notifications)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    center = _rec(ws, member, "research_center", {"name": "AI Lab", "code": "AIL",
                                                  "status": "active"})
    proj = _rec(ws, member, "research_project", {"title": "Deep Nets", "research_type": "applied",
                "research_center": str(center["id"]), "status": "active"})
    # a graduate research student joins via the generic membership entity (no research_student model)
    member_rec = _rec(ws, member, "research_team_member", {"research_project": str(proj["id"]),
                      "member_type": "graduate_research_student", "status": "active"})
    assert _retrieve(ws, member, "research_team_member",
                     member_rec["id"])["member_type"] == "graduate_research_student"
    pub = _rec(ws, member, "publication", {"title": "A Thesis on Deep Nets",
               "publication_type": "dissertation", "research_project": str(proj["id"]),
               "status": "accepted"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "publication", pub["id"], {"status": "published"})
    from apps.workflows.models import WorkflowRun
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="publication_published")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists()


# ══ U8 — Executive Analytics · Accreditation · Compliance · Portals (mirrors College C8) ═══════════
U8_ENTITIES = ["accreditation_body", "accreditation", "compliance_requirement", "compliance_record"]

# Entities forbidden by the U8 scope — portals/analytics/reporting/outcomes are owned by frozen
# platforms or represented by the four approved entities; NONE may be created.
_FORBIDDEN_U8_ENTITIES = {"portal_account", "portal_role", "portal_user", "student_portal",
                          "faculty_portal", "parent_portal", "research_portal",
                          "executive_dashboard", "dashboard", "scorecard", "executive_metric",
                          "kpi_definition", "analytics", "reporting", "learning_outcome",
                          "program_outcome", "assessment_plan", "self_study", "site_visit",
                          "audit_log", "audit_report", "regulatory_filing"}


def test_u8_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u8_accreditation_compliance_are_the_only_new_entities():
    """U8 adds exactly the 4 College-C8 institutional entities; portals/analytics/reporting/outcome
    entities are FORBIDDEN (represented by frozen platforms or the 4 approved entities)."""
    from apps.university.blueprint import UNIVERSITY_OBJECTS
    assert set(U8_ENTITIES) <= set(UNIVERSITY_OBJECTS)
    assert _FORBIDDEN_U8_ENTITIES.isdisjoint(UNIVERSITY_OBJECTS)
    # institutional vs programmatic accreditation = body_type/scope metadata; compliance variants =
    # category metadata — not separate entities
    bt = [f for f in UNIVERSITY_OBJECTS["accreditation_body"]["fields"]
          if f["slug"] == "body_type"][0]
    assert "programmatic" in bt["config"]["choices"]
    cat = [f for f in UNIVERSITY_OBJECTS["compliance_requirement"]["fields"]
           if f["slug"] == "category"][0]
    assert {"federal", "accreditor", "data_privacy"} <= set(cat["config"]["choices"])


def test_u8_portals_are_grants_only_no_portal_entities():
    """The Portal Platform owns portals; U8 configures portal_grants ONLY (student/parent/faculty),
    creating zero portal entities, and every grant's link_field exists on its entity."""
    m = build_university_manifest()
    grants = m["portal_grants"]
    ptypes = {g["portal_type"] for g in grants}
    assert {"student", "parent", "faculty"} <= ptypes
    by = {e["slug"]: {f["slug"] for f in e["fields"]} for e in m["entities"]}
    for g in grants:                                   # every link_field is a real field (isolation)
        assert g["link_field"] in by[g["entity_slug"]], (g["entity_slug"], g["link_field"])
    # no portal_* entity was created
    assert not ({"portal_account", "portal_role", "portal_user"} & set(by))


@pytest.mark.django_db
def test_u8_install_provisions_exec_accreditation_compliance_portal(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in U8_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["accreditation_granted", "compliance_overdue", "compliance_met"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["president", "compliance_officer"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["executive_scorecard", "risk_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    from apps.analytics.models import KPIDefinition
    from apps.document_templates.models import DocumentTemplate
    from apps.portal.models import PortalEntityGrant
    for kpi in ["active_accreditations", "open_compliance_items", "overdue_compliance_items"]:
        assert KPIDefinition.objects.filter(workspace_id=ws, code=kpi).exists(), kpi
    assert DocumentTemplate.objects.filter(
        workspace_id=ws, slug="accreditation_certificate").exists()
    # portals reuse the FROZEN Portal engine (portal_grants), incl. a parent + faculty grant
    assert PortalEntityGrant.objects.filter(workspace_id=ws, entity_slug="course_result",
                                            portal_type="parent").exists()
    assert PortalEntityGrant.objects.filter(workspace_id=ws, entity_slug="teaching_assignment",
                                            portal_type="faculty").exists()


@pytest.mark.django_db
def test_u8_accreditation_granted_workflow(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    body = _rec(ws, member, "accreditation_body", {"name": "ABET", "code": "ABET",
                                                   "body_type": "programmatic"})
    acc = _rec(ws, member, "accreditation", {"accreditation_body": str(body["id"]),
               "scope": "BSc CS", "status": "self_study"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "accreditation", acc["id"], {"status": "accredited"})
    from apps.workflows.models import WorkflowRun
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="accreditation_granted")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists()


@pytest.mark.django_db
def test_u8_compliance_overdue_and_met_lifecycle(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    req = _rec(ws, member, "compliance_requirement", {"name": "Annual Safety Audit",
               "category": "safety", "status": "pending"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "compliance_requirement", req["id"], {"status": "overdue"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "compliance_requirement", req["id"], {"status": "met"})
    from apps.workflows.models import WorkflowRun
    for slug in ["compliance_overdue", "compliance_met"]:
        wf = WorkflowDefinition.objects.get(workspace_id=ws, slug=slug)
        assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id).exists(), slug


@pytest.mark.django_db
def test_u8_executive_kpi_evaluates_via_analytics(template):
    """An executive KPI evaluates through the FROZEN Analytics engine (KPIService)."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    body = _rec(ws, member, "accreditation_body", {"name": "RB", "code": "RB",
                                                   "body_type": "regional"})
    for _ in range(2):
        _rec(ws, member, "accreditation", {"accreditation_body": str(body["id"]),
                                           "status": "accredited"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="active_accreditations")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_u8_president_role_home_routes(template):
    """President auto-opens the executive scorecard via the FROZEN DG-5 role-home runtime."""
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    president = Role.objects.get(workspace_id=ws, slug="president")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(president.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "executive_scorecard"


@pytest.mark.django_db
def test_u8_portal_grant_row_isolation(template):
    """A student portal user sees ONLY their own records — the FROZEN Portal engine AND-injects
    link_field=student=linked_record_id server-side. Zero package portal code."""
    from apps.portal.data_services import PortalDataService
    from apps.portal.models import PortalUser
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    stu_a = _rec(ws, member, "student", {"first_name": "Ada", "status": "enrolled"})
    stu_b = _rec(ws, member, "student", {"first_name": "Bo", "status": "enrolled"})
    _rec(ws, member, "course_result", {"student": str(stu_a["id"]), "status": "published"})
    _rec(ws, member, "course_result", {"student": str(stu_b["id"]), "status": "published"})
    pu_a = PortalUser.objects.create(
        workspace_id=ws, email="ada@u.edu", full_name="Ada", password_hash="x",
        is_active=True, is_verified=True, linked_record_id=stu_a["id"], portal_type="student")
    rows = PortalDataService.list_records(pu_a, "course_result")
    assert len(rows) == 1 and str(rows[0]["student"]) == str(stu_a["id"])   # never sees Bo's row


# ══ U9 — Enterprise hardening (additive data-integrity Rules + SLA; School 1.8 / College C9 pattern) ═
def test_u9_manifest_validates_clean():
    assert validate_solution_manifest(build_university_manifest()) == []


def test_u9_is_additive_only_no_native_no_frozen_change():
    """U9 adds ONLY the new `rules` + `sla_policies` sections reusing the generic Rules/SLA engines —
    every rule is a block_save guard (no new validation framework); University stays model-less."""
    m = build_university_manifest()
    assert m["rules"] and m["sla_policies"]
    assert all(a["type"] == "block_save" for r in m["rules"] for a in r["actions"])
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("university").get_models()) == []


@pytest.mark.django_db
def test_u9_install_provisions_rules_and_sla(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.rules.models import BusinessRule
    from apps.sla.models import SLAPolicy
    for rule in ["validate_tuition_charge_amount_before_create",
                 "validate_grant_award_amount_before_create",
                 "validate_course_result_grade_points_before_create"]:
        assert BusinessRule.objects.filter(workspace_id=ws, slug=rule).exists(), rule
    for pol in ["welfare_case_response", "incident_response", "ethics_review_turnaround",
                "compliance_turnaround", "accreditation_review"]:
        assert SLAPolicy.objects.filter(workspace_id=ws, slug=pol).exists(), pol


@pytest.mark.django_db
def test_u9_rule_blocks_negative_money(template):
    """A negative grant award is rejected by the Core Rules engine (block_save) — protects the reused
    GL posting path from an invalid journal. Valid amounts still save."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "grant", {"title": "Bad", "award_amount": "-1.00", "status": "applied"})
    ok = _rec(ws, member, "grant", {"title": "Good", "award_amount": "1000.00", "status": "applied"})
    assert ok["id"]


@pytest.mark.django_db
def test_u9_rule_blocks_out_of_range_grade(template):
    """Grade points > 4.0 are rejected — protects the CG-2 GPA calculation from corrupt input."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "course_result", {"credit_hours": 3, "grade_points": "5.0",
                                           "status": "draft"})
