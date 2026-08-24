"""
School package certification — v2.0 (Phase 1.1 student lifecycle).

Full package lifecycle through the Solution Package Platform + the real accounting integration +
the student-lifecycle automation (enroll-on-approval, promotion moves student via the related-record
capability). The package ships NO native code; every assertion is about manifest provisioning +
reuse of ERP Core engines.
"""
import uuid

import pytest

from apps.ledger.models import JournalEntry
from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.packaging import preflight
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.reporting.models import Dashboard, Report
from apps.school.blueprint import build_school_manifest, seed_school_template
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member
from apps.solution_templates.models import InstalledSolution, SolutionTemplate
from apps.studio.models import Application
from apps.workflows.models import WorkflowDefinition

LIFECYCLE_ENTITIES = ["inquiry", "promotion", "transfer", "graduation_record",
                      "withdrawal", "alumni", "student_status_history"]


@pytest.fixture
def template(db):
    return seed_school_template()


def _install(ws):
    return sol.install(template_id=seed_school_template().id, workspace_id=ws, installed_by=None)


def _rec(ws, member, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=member, entity=entity, data=data)


def _students(ws, member):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    return RecordService.list_records(workspace_id=ws, member=member, entity=entity)


# ── manifest + preflight ──────────────────────────────────────────────────────
ACADEMIC_ENTITIES = ["campus", "term", "academic_calendar_event", "curriculum",
                     "subject_assignment", "lesson_plan", "promotion_rule"]


@pytest.mark.django_db
def test_preflight_clean_and_v2():
    m = build_school_manifest()
    assert m["package"]["version"] == "2.7.0"
    res = preflight.preflight(m, workspace_id=uuid.uuid4())
    assert res.ok, res.errors
    assert "student_lifecycle" in res.requirements["provides_capabilities"]


@pytest.mark.django_db
def test_install_provisions_lifecycle(template):
    ws = uuid.uuid4()
    installed = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert installed.installed_version == "2.7.0"
    assert EntityDefinition.objects.filter(workspace_id=ws).count() >= 34
    for slug in LIFECYCLE_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="enroll_on_approval").exists()
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="promotion_processed").exists()
    assert Role.objects.filter(workspace_id=ws, slug="registrar").exists()
    assert Report.objects.filter(workspace_id=ws, slug="admissions_funnel_report").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="admissions_dashboard").exists()
    assert Application.objects.filter(workspace_id=ws, slug="school").exists()


@pytest.mark.django_db
def test_install_provisions_academic_structure(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ACADEMIC_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="lesson_plan_review").exists()
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="publish_results").exists()
    assert Role.objects.filter(workspace_id=ws, slug="academic_coordinator").exists()
    assert Report.objects.filter(workspace_id=ws, slug="teacher_workload_report").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="academic_planning_dashboard").exists()


# ── lifecycle automation (end-to-end through the workflow engine) ────────────
@pytest.mark.django_db
def test_enroll_on_approval_creates_student(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    app_entity = EntityDefinition.objects.get(workspace_id=ws, slug="admission_application")

    with django_capture_on_commit_callbacks(execute=True):
        app = RecordService.create_record(
            workspace_id=ws, member=member, entity=app_entity,
            data={"applicant_name": "Jane Doe", "gender": "female", "status": "submitted"})
    assert _students(ws, member) == []                      # not enrolled yet

    with django_capture_on_commit_callbacks(execute=True):
        RecordService.update_record(workspace_id=ws, member=member, entity=app_entity,
                                    record_id=app["id"], data={"status": "approved"})

    students = _students(ws, member)
    assert len(students) == 1                               # student auto-created
    assert students[0]["first_name"] == "Jane Doe"
    assert students[0]["status"] == "enrolled"
    # application closed → re-approval would not double-create
    refreshed = RecordService.retrieve_record(workspace_id=ws, member=member, entity=app_entity,
                                              record_id=app["id"])
    assert refreshed["status"] == "enrolled"


@pytest.mark.django_db
def test_promotion_moves_student_to_new_class(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)

    class_a = _rec(ws, member, "school_class", {"name": "Grade 1-A"})
    class_b = _rec(ws, member, "school_class", {"name": "Grade 2-A"})
    student = _rec(ws, member, "student",
                   {"first_name": "Sam", "status": "enrolled",
                    "school_class": str(class_a["id"])})
    promo = _rec(ws, member, "promotion",
                 {"student": str(student["id"]), "from_class": str(class_a["id"]),
                  "to_class": str(class_b["id"]), "status": "pending"})

    promo_entity = EntityDefinition.objects.get(workspace_id=ws, slug="promotion")
    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    with django_capture_on_commit_callbacks(execute=True):
        RecordService.update_record(workspace_id=ws, member=member, entity=promo_entity,
                                    record_id=promo["id"], data={"status": "completed"})

    moved = RecordService.retrieve_record(workspace_id=ws, member=member, entity=student_entity,
                                          record_id=student["id"])
    assert str(moved["school_class"]) == str(class_b["id"])   # related-record update worked


@pytest.mark.django_db
def test_fee_invoice_still_posts_journal(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "fee_invoice", {"amount": "1500.00", "status": "issued"})
    entries = JournalEntry.objects.filter(workspace_id=ws, source_module="school")
    assert entries.count() == 1
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entries.first().lines.all()}
    assert lines["1100"][0] == 1500 and lines["4100"][1] == 1500


# ── upgrade v1 → v2 (declarative migration + additive entities) ──────────────
def _v1_manifest():
    return {
        "schema_version": 1,
        "package": {"slug": "school", "name": "School", "version": "1.0.0"},
        "entities": [{"slug": "student", "name": "Student", "plural_name": "Students", "fields": [
            {"slug": "admission_no", "name": "Admission No", "field_type": "auto_number",
             "is_promoted": True, "is_unique": True, "config": {"prefix": "ADM-"}},
            {"slug": "first_name", "name": "First Name", "field_type": "text", "is_promoted": True},
            {"slug": "status", "name": "Status", "field_type": "status",
             "is_promoted": True, "config": {"choices": ["applicant", "enrolled"]}}]}],
    }


@pytest.mark.django_db
def test_upgrade_v1_to_v2_adds_entities_and_runs_migration():
    ws = uuid.uuid4()
    v1 = SolutionTemplate.objects.create(slug="school_v1_demo", name="School v1", version="1.0.0",
                                         is_published=True, manifest=_v1_manifest())
    inst = sol.install(template_id=v1.id, workspace_id=ws, installed_by=None)
    assert not EntityDefinition.objects.filter(workspace_id=ws, slug="inquiry").exists()

    upgraded = sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                           manifest=build_school_manifest(), version="2.7.0")
    assert upgraded.installed_version == "2.7.0"
    assert upgraded.applied_migrations == [
        "2.0.0", "2.1.0", "2.2.0", "2.3.0", "2.4.0", "2.5.0", "2.6.0", "2.7.0"]  # all ran
    # additive applier added the lifecycle + academic entities on upgrade
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="inquiry").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="curriculum").exists()
    student = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    fields = set(FieldDefinition.objects.filter(
        workspace_id=ws, entity_id=student.id).values_list("slug", flat=True))
    assert {"emergency_contact", "uses_transport", "nationality"} <= fields


@pytest.mark.django_db
def test_rollback_keeps_schema(template):
    ws = uuid.uuid4()
    v1 = SolutionTemplate.objects.create(slug="school_v1_demo", name="School v1", version="1.0.0",
                                         is_published=True, manifest=_v1_manifest())
    inst = sol.install(template_id=v1.id, workspace_id=ws, installed_by=None)
    sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                manifest=build_school_manifest(), version="2.7.0")
    rolled = sol.rollback(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert rolled.installed_version == "1.0.0"
    # data safety: lifecycle entities + new fields are NOT removed
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="inquiry").exists()


# ── package lifecycle ─────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_disable_enable_round_trip(template):
    ws = uuid.uuid4()
    inst = _install(ws)
    sol.uninstall(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert InstalledSolution.objects.get(id=inst.id).status == "disabled"
    assert WorkflowDefinition.objects.get(
        workspace_id=ws, slug="enroll_on_approval").status == "archived"
    sol.enable(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert WorkflowDefinition.objects.get(
        workspace_id=ws, slug="enroll_on_approval").status == "active"


@pytest.mark.django_db
def test_soft_uninstall_preserves_data(template):
    ws = uuid.uuid4()
    inst = _install(ws)
    n = EntityDefinition.objects.filter(workspace_id=ws).count()
    sol.uninstall(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert EntityDefinition.objects.filter(workspace_id=ws).count() == n   # defs preserved


@pytest.mark.django_db
def test_hard_uninstall_deactivates_definitions(template):
    ws = uuid.uuid4()
    inst = _install(ws)
    sol.uninstall(installed_id=inst.id, workspace_id=ws, actor_id=None, hard=True)
    assert EntityDefinition.objects.filter(
        workspace_id=ws, slug="student", is_active=False).exists()   # def off, data kept


@pytest.mark.django_db
def test_school_coexists_with_crm():
    from apps.crm.blueprint import seed_crm_template
    ws = uuid.uuid4()
    sol.install(template_id=seed_crm_template().id, workspace_id=ws, installed_by=None)
    sol.install(template_id=seed_school_template().id, workspace_id=ws, installed_by=None)
    assert InstalledSolution.objects.filter(workspace_id=ws, status="active").count() == 2
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="inquiry").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="lead").exists()


@pytest.mark.django_db
def test_seed_is_idempotent():
    seed_school_template()
    seed_school_template()
    assert SolutionTemplate.objects.filter(slug="school").count() == 1
    assert SolutionTemplate.objects.get(slug="school").version == "2.7.0"


# ── Phase 1.3: Fee Management depth (School as PURE manifest consumer of F2/F3) ──────────
FEE_DEPTH_ENTITIES = ["fee_category", "fee_installment_plan", "fee_discount", "fee_scholarship",
                      "fee_waiver", "fee_refund", "fee_writeoff"]
FEE_DEPTH_WORKFLOWS = ["fee_plan_create", "fee_discount_apply", "fee_scholarship_apply",
                       "fee_waiver_apply", "fee_refund_process", "fee_writeoff_process"]


@pytest.mark.django_db
def test_install_provisions_fee_depth(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in FEE_DEPTH_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for slug in FEE_DEPTH_WORKFLOWS:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert Role.objects.filter(workspace_id=ws, slug="finance_manager").exists()
    assert Dashboard.objects.filter(workspace_id=ws, slug="finance_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="scholarships_report").exists()


@pytest.mark.django_db
def test_fee_discount_posts_credit(template, django_capture_on_commit_callbacks):
    """Approving a School fee_discount fires the Core Credit Engine (F3): a CreditNote is posted
    with a balanced GL entry (Dr Discounts 4200 / Cr A/R 1100). Zero School accounting code."""
    from apps.credits.models import CreditNote
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    disc = _rec(ws, member, "fee_discount", {"amount": "200.00", "reason": "Sibling discount",
                                             "status": "requested"})
    with django_capture_on_commit_callbacks(execute=True):
        ent = EntityDefinition.objects.get(workspace_id=ws, slug="fee_discount")
        RecordService.update_record(workspace_id=ws, member=member, entity=ent,
                                    record_id=disc["id"], data={"status": "approved"})
    note = CreditNote.objects.filter(workspace_id=ws, kind="discount").first()
    assert note is not None and note.amount == 200
    entry = JournalEntry.objects.get(id=note.journal_entry_id)
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["4200"][0] == 200 and lines["1100"][1] == 200
    # request marked applied by the workflow
    refreshed = RecordService.retrieve_record(workspace_id=ws, member=member, entity=ent,
                                              record_id=disc["id"])
    assert refreshed["status"] == "applied"


@pytest.mark.django_db
def test_fee_installment_plan_builds_schedule(template, django_capture_on_commit_callbacks):
    """Approving a School fee_installment_plan fires the Core Collections Engine (F2): a plan +
    due schedule are created. Zero School collections code."""
    from apps.collections_engine.models import Installment, InstallmentPlan
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    plan_req = _rec(ws, member, "fee_installment_plan",
                    {"total_amount": "900.00", "num_installments": 3, "frequency": "monthly",
                     "start_date": "2026-01-15", "status": "draft"})
    with django_capture_on_commit_callbacks(execute=True):
        ent = EntityDefinition.objects.get(workspace_id=ws, slug="fee_installment_plan")
        RecordService.update_record(workspace_id=ws, member=member, entity=ent,
                                    record_id=plan_req["id"], data={"status": "approved"})
    plan = InstallmentPlan.objects.filter(workspace_id=ws).first()
    assert plan is not None and plan.num_installments == 3
    assert Installment.objects.filter(workspace_id=ws, plan_id=plan.id).count() == 3


@pytest.mark.django_db
def test_fee_refund_posts_refund(template, django_capture_on_commit_callbacks):
    """Approving a School fee_refund fires the Core Credit Engine refund path (Dr 4100 / Cr Cash)."""
    from apps.credits.models import CreditNote
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ref = _rec(ws, member, "fee_refund", {"amount": "120.00", "method": "bank",
                                          "reason": "Overpayment", "status": "requested"})
    with django_capture_on_commit_callbacks(execute=True):
        ent = EntityDefinition.objects.get(workspace_id=ws, slug="fee_refund")
        RecordService.update_record(workspace_id=ws, member=member, entity=ent,
                                    record_id=ref["id"], data={"status": "approved"})
    note = CreditNote.objects.filter(workspace_id=ws, kind="refund").first()
    assert note is not None and note.amount == 120
    lines = {ln.account.code: (ln.debit, ln.credit)
             for ln in JournalEntry.objects.get(id=note.journal_entry_id).lines.all()}
    assert lines["4100"][0] == 120 and lines["1000"][1] == 120


# ── Phase 1.4: Documents (School as PURE consumer of the Core Document Engine) ───────────
DOC_TEMPLATE_SLUGS = ["admission_letter", "student_id_card", "report_card", "transcript",
                      "transfer_certificate", "graduation_certificate", "bonafide_certificate",
                      "fee_invoice_document", "fee_receipt", "statement_of_account",
                      "scholarship_letter", "refund_document", "library_card",
                      "book_issue_receipt", "transport_pass", "hostel_allocation",
                      "teacher_appointment", "assignment_letter"]


@pytest.mark.django_db
def test_install_provisions_document_templates(template):
    from apps.document_templates.models import DocumentTemplate
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in DOC_TEMPLATE_SLUGS:
        assert DocumentTemplate.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    # a healthy library of templates provisioned
    assert DocumentTemplate.objects.filter(workspace_id=ws).count() >= 40


@pytest.mark.django_db
def test_fee_payment_auto_generates_receipt(template, django_capture_on_commit_callbacks):
    """Recording a fee_payment fires the Core document engine (action_generate_document): a
    receipt PDF is rendered + attached to the payment record. Zero School document code."""
    from apps.documents.models import Document
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        pay = _rec(ws, member, "fee_payment", {"amount": "500.00", "method": "cash"})
    docs = Document.objects.filter(workspace_id=ws, record_id=pay["id"], deleted_at__isnull=True)
    assert docs.filter(name__startswith="fee_receipt").exists()
    # GL still posted (Dr Cash / Cr A/R) — document generation did not disturb accounting
    assert JournalEntry.objects.filter(workspace_id=ws, source_module="school").count() == 1


@pytest.mark.django_db
def test_document_template_renders_pdf(template):
    from apps.document_templates.models import DocumentTemplate
    from apps.document_templates.services import render
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    inv = _rec(ws, member, "fee_invoice", {"amount": "1200.00", "status": "issued"})
    tpl = DocumentTemplate.objects.get(workspace_id=ws, slug="fee_invoice_document")
    pdf = render(tpl, workspace_id=ws, record_id=inv["id"], member=member)
    assert isinstance(pdf, bytes) and pdf[:4] == b"%PDF"


# ── Phase 1.8: Enterprise hardening — validation rules + SLA (reuse Rules + SLA engines) ──────
@pytest.mark.django_db
def test_install_provisions_validation_and_sla(template):
    from apps.rules.models import BusinessRule
    from apps.sla.models import SLAPolicy
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert BusinessRule.objects.filter(workspace_id=ws).count() >= 15
    for slug in ["safeguarding_response", "counselling_response", "incident_response"]:
        assert SLAPolicy.objects.filter(workspace_id=ws, slug=slug).exists(), slug


@pytest.mark.django_db
def test_validation_blocks_nonpositive_amount(template):
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    # a zero-amount fee invoice is blocked by the data-integrity rule (protects GL posting)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "fee_invoice", {"amount": "0", "status": "draft"})
    # a valid amount saves fine
    ok = _rec(ws, member, "fee_invoice", {"amount": "1000", "status": "draft"})
    assert ok["id"]


@pytest.mark.django_db
def test_sla_attaches_on_safeguarding(template):
    from apps.sla.models import SLARecord
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "S", "status": "enrolled"})
    sg = _rec(ws, member, "safeguarding_record",
              {"student": str(student["id"]), "concern_type": "welfare", "severity": "high",
               "status": "open"})
    # the SLA engine auto-attached a resolution timer on create (enterprise child-safety responsiveness)
    assert SLARecord.objects.filter(workspace_id=ws, record_id=sg["id"]).exists()


# ── Phase 1.7: Reporting, Analytics & Executive Intelligence (reuse reporting/analytics/dashboard) ──
@pytest.mark.django_db
def test_install_provisions_kpis_and_executive_dashboard(template):
    from apps.analytics.models import KPIDefinition
    from apps.reporting.models import Dashboard
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    kpis = KPIDefinition.objects.filter(workspace_id=ws)
    assert kpis.count() >= 13
    # spanning the KPI categories a School exec expects
    assert set(kpis.values_list("category", flat=True)) >= {"academic", "financial",
                                                            "operations", "risk"}
    for code in ["students_enrolled", "fee_collected", "high_risk_students"]:
        assert kpis.filter(code=code).exists(), code
    assert Dashboard.objects.filter(workspace_id=ws, slug="executive_dashboard").exists()
    # administrator auto-routes to the executive dashboard (DG-5)
    from apps.permissions.models import Role
    from apps.studio.services import resolve_home_layout
    admin_role = Role.objects.get(workspace_id=ws, slug="school_administrator")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(admin_role.id)])
    assert layout.widgets[0]["config"]["dashboard_slug"] == "executive_dashboard"


@pytest.mark.django_db
def test_kpi_evaluates_via_analytics_engine(template):
    """A School KPI computes through the reused Analytics Engine (NQL aggregate) — no new engine."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    _rec(ws, member, "student", {"first_name": "E1", "status": "enrolled"})
    _rec(ws, member, "student", {"first_name": "E2", "status": "enrolled"})
    _rec(ws, member, "student", {"first_name": "A1", "status": "applicant"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="students_enrolled")
    result = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert int(float(result["value"])) == 2   # only enrolled students counted (NQL WHERE works)


# ── Phase 1.6: Student Services (pure manifest; reuses workflow/notification/portal/audit Core) ──
STUDENT_SERVICES_ENTITIES = [
    "leave_request", "attendance_correction", "behaviour_category", "behaviour_incident",
    "disciplinary_action", "counselling_referral", "counselling_session", "medical_profile",
    "medical_visit", "medical_alert", "health_screening", "learning_support", "iep",
    "student_club", "club_membership", "sport", "competition", "achievement", "award",
    "student_activity", "student_leadership", "house", "career_counselling", "internship",
    "student_note", "student_alert", "student_risk_indicator", "visitor_log", "parent_meeting",
    "lost_and_found", "incident_report", "safeguarding_record", "id_card_request", "gate_pass",
]


@pytest.mark.django_db
def test_install_provisions_student_services(template):
    from apps.reporting.models import Dashboard, Report
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in STUDENT_SERVICES_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for role in ["class_teacher", "counsellor", "school_nurse", "medical_officer",
                 "sports_coordinator", "club_coordinator"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["counsellor_dashboard", "medical_dashboard", "activities_dashboard",
                 "welfare_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    for rpt in ["behaviour_report", "medical_visits_report", "counselling_report",
                "safeguarding_report"]:
        assert Report.objects.filter(workspace_id=ws, slug=rpt).exists(), rpt


@pytest.mark.django_db
def test_student_services_workflow_and_portal(template, django_capture_on_commit_callbacks):
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "Kid", "status": "enrolled"})
    cat = _rec(ws, member, "behaviour_category",
               {"name": "Punctuality", "category_type": "demerit", "default_points": 2})
    # Behaviour incident logged → its notify workflow fires.
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "behaviour_incident",
             {"student": str(student["id"]), "category": str(cat["id"]), "severity": "low",
              "points": 2, "status": "logged"})
    wd = WorkflowDefinition.objects.get(workspace_id=ws, slug="behaviour_incident_logged")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wd.id).exists()

    # Family portal sees the student's behaviour incident (per-student scope), reusing Portal Engine.
    from apps.portal.data_services import PortalDataService
    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    parent = _portal_user(ws, student_entity.id, student["id"], "parent")
    incidents = PortalDataService.list_records(parent, "behaviour_incident")
    assert len(incidents) == 1
    # confidential services are NOT exposed to the portal
    from apps.portal.data_services import PortalAccessError
    with pytest.raises(PortalAccessError):
        PortalDataService.list_records(parent, "counselling_session")
    with pytest.raises(PortalAccessError):
        PortalDataService.list_records(parent, "safeguarding_record")


@pytest.mark.django_db
def test_leave_request_approval_workflow(template, django_capture_on_commit_callbacks):
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    student = _rec(ws, member, "student", {"first_name": "L", "status": "enrolled"})
    lr = _rec(ws, member, "leave_request",
              {"student": str(student["id"]), "leave_type": "sick", "from_date": "2026-06-01",
               "status": "requested"})
    ent = EntityDefinition.objects.get(workspace_id=ws, slug="leave_request")
    with django_capture_on_commit_callbacks(execute=True):
        RecordService.update_record(workspace_id=ws, member=member, entity=ent,
                                    record_id=lr["id"], data={"status": "approved"})
    wd = WorkflowDefinition.objects.get(workspace_id=ws, slug="leave_request_approved")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wd.id).exists()


# ── Phase 1.5: Portal experience (School configures the generic Portal Engine — metadata only) ──
@pytest.mark.django_db
def test_install_provisions_portal_grants(template):
    from apps.portal.models import PortalEntityGrant
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    grants = PortalEntityGrant.objects.filter(workspace_id=ws)
    assert grants.filter(portal_type="student").count() >= 15
    assert grants.filter(portal_type="parent").count() >= 15
    # indirect (class) scoping configured for class-level data
    tt = grants.get(workspace_id=ws, entity_slug="timetable_entry", portal_type="student")
    assert tt.link_field == "school_class" and tt.link_source == "school_class"
    # per-student direct scoping
    att = grants.get(workspace_id=ws, entity_slug="attendance", portal_type="student")
    assert att.link_field == "student" and att.link_source == ""


def _portal_user(ws, student_entity_id, student_id, ptype):
    from apps.portal.models import PortalUser
    return PortalUser.objects.create(
        workspace_id=ws, email=f"{ptype}-{uuid.uuid4().hex[:6]}@x.com", full_name=ptype.title(),
        password_hash="x", is_active=True, is_verified=True,
        linked_entity_id=student_entity_id, linked_record_id=student_id, portal_type=ptype)


@pytest.mark.django_db
def test_student_portal_scoped_data(template):
    """A student portal user sees ONLY their own per-student rows (direct scope) and only their
    class's timetable (indirect scope) — server-enforced, reusing the generic Portal Engine."""
    from apps.portal.data_services import PortalAccessError, PortalDataService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    class_a = _rec(ws, member, "school_class", {"name": "1-A"})
    class_b = _rec(ws, member, "school_class", {"name": "1-B"})
    s1 = _rec(ws, member, "student", {"first_name": "S1", "school_class": str(class_a["id"]),
                                      "status": "enrolled"})
    s2 = _rec(ws, member, "student", {"first_name": "S2", "school_class": str(class_b["id"]),
                                      "status": "enrolled"})
    _rec(ws, member, "attendance", {"student": str(s1["id"]), "status": "present",
                                    "date": "2026-06-01"})
    _rec(ws, member, "attendance", {"student": str(s2["id"]), "status": "absent",
                                    "date": "2026-06-01"})
    _rec(ws, member, "timetable_entry", {"school_class": str(class_a["id"]), "period": 1})
    _rec(ws, member, "timetable_entry", {"school_class": str(class_b["id"]), "period": 1})

    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    pu = _portal_user(ws, student_entity.id, s1["id"], "student")

    # direct scope: only S1's attendance
    att = PortalDataService.list_records(pu, "attendance")
    assert len(att) == 1 and str(att[0]["student"]) == str(s1["id"])
    # own profile via link_field="id"
    prof = PortalDataService.list_records(pu, "student")
    assert len(prof) == 1 and str(prof[0]["id"]) == str(s1["id"])
    # indirect scope: only class A's timetable
    tt = PortalDataService.list_records(pu, "timetable_entry")
    assert len(tt) == 1 and str(tt[0]["school_class"]) == str(class_a["id"])
    # a non-granted entity is denied
    with pytest.raises(PortalAccessError):
        PortalDataService.list_records(pu, "teacher")


@pytest.mark.django_db
def test_parent_portal_reads_child_data(template):
    from apps.portal.data_services import PortalDataService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    child = _rec(ws, member, "student", {"first_name": "Kid", "status": "enrolled"})
    _rec(ws, member, "fee_invoice", {"student": str(child["id"]), "amount": "500", "status": "issued"})
    student_entity = EntityDefinition.objects.get(workspace_id=ws, slug="student")
    parent = _portal_user(ws, student_entity.id, child["id"], "parent")
    invoices = PortalDataService.list_records(parent, "fee_invoice")
    assert len(invoices) == 1 and str(invoices[0]["student"]) == str(child["id"])


@pytest.mark.django_db
def test_role_dashboards_auto_route(template):
    """DG-5: every operational role gets a role-scoped HomeLayout bound to its role id, so
    resolve_home_layout auto-opens the role's dashboard after login — no manual selection."""
    from apps.permissions.models import Role
    from apps.reporting.models import Dashboard
    from apps.studio.models import HomeLayout
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)

    role_homes = HomeLayout.objects.filter(workspace_id=ws, scope="role")
    assert role_homes.count() >= 12   # one per operational role
    # service-role dashboards were provisioned
    for slug in ["library_dashboard", "transport_dashboard", "hostel_dashboard",
                 "finance_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=slug).exists(), slug

    # each role resolves to its intended dashboard
    for role_slug, dash_slug in [("accountant", "finance_dashboard"),
                                 ("teacher", "academic_dashboard"),
                                 ("librarian", "library_dashboard"),
                                 ("transport_manager", "transport_dashboard"),
                                 ("registrar", "admissions_dashboard")]:
        role = Role.objects.get(workspace_id=ws, slug=role_slug)
        layout = resolve_home_layout(workspace_id=ws, role_ids=[str(role.id)])
        assert layout is not None and layout.scope == "role", role_slug
        assert layout.widgets[0]["config"]["dashboard_slug"] == dash_slug, role_slug

    # a user with no custom role (system owner) falls back to the app-scoped home
    app = Application.objects.get(workspace_id=ws, slug="school")
    fallback = resolve_home_layout(workspace_id=ws, role_ids=[], app_id=str(app.id))
    assert fallback is not None and fallback.scope == "app"


@pytest.mark.django_db
def test_fee_depth_nav_and_manifest_valid(template):
    m = build_school_manifest()
    nav_targets = {item["target"] for grp in m["navigations"][0]["tree"] for item in grp["items"]}
    for slug in FEE_DEPTH_ENTITIES:
        assert slug in nav_targets, slug
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(m) == []


@pytest.mark.django_db
def test_nav_and_app_wire_lifecycle_entities(template):
    """Frontend wiring: the lifecycle entities are reachable through the School app navigation
    (the generic runtime renders them — no bespoke React)."""
    m = build_school_manifest()
    nav_targets = {item["target"] for grp in m["navigations"][0]["tree"]
                   for item in grp["items"]}
    for slug in LIFECYCLE_ENTITIES:
        assert slug in nav_targets, slug
    assert set(LIFECYCLE_ENTITIES) <= set(m["applications"][0]["included_entity_slugs"])
