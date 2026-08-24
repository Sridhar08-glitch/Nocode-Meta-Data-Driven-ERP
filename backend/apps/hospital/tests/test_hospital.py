"""
Hospital package — Phase H1 (Master Data & Facility) certification.

The 1st clinical package. Pure manifest: every assertion is about manifest provisioning + reuse of the
ERP Core engines (metadata/RBAC/reporting/analytics/dashboards/numbering) — zero native code. Validates
generalization (provider/ward/bed/payer *_type metadata; no per-variant entities), independence
(`requires_packages=[]`), and coexistence with the frozen Education packages.
"""
import uuid

import pytest

from apps.hospital.blueprint import build_hospital_manifest, seed_hospital_template
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

H1_ENTITIES = [
    "facility", "clinical_department", "ward", "bed", "provider", "specialty",
    "service_catalog", "payer", "diagnosis_code", "procedure_code", "drug_formulary",
]

# Per-variant entities the generalization rule FORBIDS — represented by *_type metadata.
_FORBIDDEN_H1_ENTITIES = {
    "doctor", "surgeon", "consultant", "resident", "physician",       # → provider(provider_type)
    "icu", "er", "emergency_ward", "maternity_ward", "pediatric_ward",  # → ward(ward_type)
    "icu_bed", "ward_bed",                                            # → bed(bed_type)
    "government_payer", "insurance_company", "private_payer",         # → payer(payer_type)
    "medical_code",                                                   # diagnosis/procedure kept separate
    "provider_specialty",                                             # → specialty + provider lookup
}


@pytest.fixture
def template(db):
    return seed_hospital_template()


def _rec(ws, member, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=member, entity=entity, data=data)


def _retrieve(ws, member, slug, rid):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity, record_id=rid)


def _update(ws, member, slug, rid, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.update_record(workspace_id=ws, member=member, entity=entity,
                                       record_id=rid, data=data)


# ── manifest + governance ─────────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_package_is_independent_first_clinical_package():
    pkg = build_hospital_manifest()["package"]
    assert pkg["slug"] == "hospital" and pkg["version"] == "1.13.0"
    assert pkg["requires_packages"] == []                          # installs standalone on Core
    assert {p["slug"] for p in pkg["optional_packages"]} == {"inventory", "assets"}
    assert "health_information_system" in pkg["provides_capabilities"]


def test_h1_is_generalized_no_per_variant_entities():
    """Generalization rule: provider/ward/bed/payer carry *_type metadata; NO doctor/surgeon,
    icu/er/maternity, icu_bed, or government/private payer entities. Diagnosis + procedure codes are
    kept as SEPARATE terminology masters (no generic medical_code)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H1_ENTITIES) <= set(HOSPITAL_OBJECTS)               # the 11 H1 masters are all present
    assert _FORBIDDEN_H1_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    for ent, disc, kinds in [
        ("provider", "provider_type", ("physician", "surgeon", "nurse")),
        ("ward", "ward_type", ("icu", "emergency", "maternity")),
        ("bed", "bed_type", ("icu", "general")),
        ("payer", "payer_type", ("government", "private_insurance", "self_pay")),
    ]:
        fld = [f for f in HOSPITAL_OBJECTS[ent]["fields"] if f["slug"] == disc][0]
        assert set(kinds) <= set(fld["config"]["choices"]), ent
    # diagnosis + procedure kept separate (no generic medical_code)
    assert {"diagnosis_code", "procedure_code"} <= set(HOSPITAL_OBJECTS)
    assert "medical_code" not in HOSPITAL_OBJECTS


def test_hospital_is_pure_manifest_no_native_models():
    """The hospital package is model-less: all behaviour (incl. H3 workflows) is manifest config over
    the frozen platforms — zero native Django models/services/executors."""
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("hospital").get_models()) == []
    # every workflow step reuses a frozen Core executor (no package-specific engine). H9 billing
    # reuses the Finance-Platform executors (GL / Settlement) + the Document engine — still all frozen
    # Core, still zero native Hospital code.
    allowed = {"action_guard", "action_update_record", "action_send_notification", "condition",
               "action_post_journal", "action_register_settlement_document", "action_auto_allocate",
               "action_auto_reconcile", "action_generate_document"}
    for wf in build_hospital_manifest()["workflows"]:
        assert all(s["step_type"] in allowed for s in wf["steps"]), wf["slug"]


# ── provisioning + reuse ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_install_provisions_master_data(template):
    ws = uuid.uuid4()
    installed = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert installed.installed_version == "1.13.0"
    for slug in H1_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for role in ["hospital_administrator", "master_data_manager", "medical_staff_office"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    for dash in ["master_data_dashboard", "bed_capacity_dashboard"]:
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    assert Report.objects.filter(workspace_id=ws, slug="providers_report").exists()
    assert Application.objects.filter(workspace_id=ws, slug="hospital").exists()


@pytest.mark.django_db
def test_facility_ward_bed_hierarchy(template):
    """Facility → ward → bed hierarchy; generic ward_type/bed_type carry the variant, and the bed
    has its own status lifecycle."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    fac = _rec(ws, member, "facility", {"name": "Central Hospital", "code": "CH",
                                        "facility_type": "hospital", "status": "active"})
    ward = _rec(ws, member, "ward", {"name": "ICU-1", "code": "ICU1", "ward_type": "icu",
                                     "facility": str(fac["id"]), "status": "active"})
    bed = _rec(ws, member, "bed", {"label": "ICU-1-B1", "bed_type": "icu",
                                   "ward": str(ward["id"]), "status": "available"})
    assert str(ward["facility"]) == str(fac["id"]) and ward["ward_type"] == "icu"
    ref = _retrieve(ws, member, "bed", bed["id"])
    assert ref["bed_type"] == "icu" and str(ref["ward"]) == str(ward["id"])
    assert ref["status"] == "available"


@pytest.mark.django_db
def test_provider_is_generic_with_type_metadata(template):
    """A surgeon is a provider with provider_type=surgeon — not a separate entity."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    spec = _rec(ws, member, "specialty", {"name": "Cardiothoracic Surgery", "code": "CTS",
                                          "category": "surgical", "status": "active"})
    prov = _rec(ws, member, "provider", {"name": "Dr Ada", "provider_type": "surgeon",
                "specialty": str(spec["id"]), "license_no": "L-123", "status": "active"})
    ref = _retrieve(ws, member, "provider", prov["id"])
    assert ref["provider_type"] == "surgeon" and str(ref["specialty"]) == str(spec["id"])
    assert ref["license_no"] == "L-123"


@pytest.mark.django_db
def test_diagnosis_and_procedure_codes_are_separate(template):
    """Diagnosis + procedure codes are separate terminology masters (user-ratified — no generic
    medical_code); each keyed by its own natural code."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    dx = _rec(ws, member, "diagnosis_code", {"code": "I21.9", "description": "Acute MI",
              "code_system": "icd10", "status": "active"})
    px = _rec(ws, member, "procedure_code", {"code": "33533", "description": "CABG",
              "code_system": "cpt", "is_billable": True, "status": "active"})
    assert _retrieve(ws, member, "diagnosis_code", dx["id"])["code"] == "I21.9"
    assert _retrieve(ws, member, "procedure_code", px["id"])["code"] == "33533"


@pytest.mark.django_db
def test_kpi_evaluates_via_analytics(template):
    """A master-data KPI evaluates through the FROZEN Analytics engine (KPIService)."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    fac = _rec(ws, member, "facility", {"name": "F", "code": "F1", "status": "active"})
    ward = _rec(ws, member, "ward", {"name": "W", "code": "W1", "facility": str(fac["id"]),
                                     "status": "active"})
    for lbl, st in [("B1", "available"), ("B2", "available"), ("B3", "occupied")]:
        _rec(ws, member, "bed", {"label": lbl, "ward": str(ward["id"]), "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="available_beds")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_role_home_routes(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    admin = Role.objects.get(workspace_id=ws, slug="master_data_manager")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(admin.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "master_data_dashboard"


# ── lifecycle + coexistence ────────────────────────────────────────────────────
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
    seed_hospital_template()
    seed_hospital_template()
    from apps.solution_templates.models import SolutionTemplate
    assert SolutionTemplate.objects.filter(slug="hospital").count() == 1


@pytest.mark.django_db
def test_hospital_coexists_with_university_in_separate_workspaces():
    """The clinical package coexists with the frozen Education packages — each installs cleanly into
    its own workspace with no cross-workspace bleed."""
    from apps.university.blueprint import seed_university_template
    ws_h, ws_u = uuid.uuid4(), uuid.uuid4()
    sol.install(template_id=seed_hospital_template().id, workspace_id=ws_h, installed_by=None)
    sol.install(template_id=seed_university_template().id, workspace_id=ws_u, installed_by=None)
    assert EntityDefinition.objects.filter(workspace_id=ws_h, slug="provider").exists()
    assert not EntityDefinition.objects.filter(workspace_id=ws_u, slug="provider").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws_u, slug="program").exists()
    assert not EntityDefinition.objects.filter(workspace_id=ws_h, slug="program").exists()


@pytest.mark.django_db
def test_nav_wires_master_data(template):
    m = build_hospital_manifest()
    nav_targets = {item["target"] for grp in m["navigations"][0]["tree"] for item in grp["items"]}
    for slug in ["facility", "ward", "bed", "provider", "payer"]:
        assert slug in nav_targets, slug
    assert set(H1_ENTITIES) <= set(m["applications"][0]["included_entity_slugs"])


# ══ H2 — Patient Administration & Registration ═════════════════════════════════════════════════════
H2_ENTITIES = ["patient", "patient_contact", "insurance_policy"]

# Entities NO phase ever creates (patient identity ≠ visits; contacts/guarantor are contact_type
# metadata) + ``patient_alert`` which is PERMANENTLY rejected (a derived presentation layer over its
# owning modules). NOTE: ``allergy`` and ``encounter`` are NOT here — they are legitimately owned by
# H4 (the architectural correction moved allergy to the clinical record); the H4 tests assert that.
_FORBIDDEN_H2_ENTITIES = {"registration", "visit", "patient_visit", "episode",
                          "next_of_kin", "emergency_contact", "guarantor", "patient_identifier",
                          "inpatient_patient", "outpatient_patient", "insurance_claim",
                          "patient_alert"}   # → PERMANENTLY REJECTED (derived presentation layer)


def test_h2_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h2_patient_admin_entities_and_no_clinical_or_visit_entity():
    """H2 = exactly 3 patient-administration entities; owns patient IDENTITY not visits (no encounter/
    visit/registration) and NO clinical record — allergy is H4, patient_alert is rejected; contacts +
    insurance are generic (*_type)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H2_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H2_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)   # incl. allergy + patient_alert absent
    # OP/IP is encounter-level → patient carries only a generic category, never a patient_type OP/IP
    pf = {f["slug"] for f in HOSPITAL_OBJECTS["patient"]["fields"]}
    assert "patient_category" in pf and "patient_type" not in pf
    for ent, disc in [("patient_contact", "contact_type"), ("insurance_policy", "coverage_type")]:
        assert any(f["slug"] == disc for f in HOSPITAL_OBJECTS[ent]["fields"]), ent
    # insurance_policy is coverage-only — NO claim/preauth/payment fields (those are H9/Financial)
    ipf = {f["slug"] for f in HOSPITAL_OBJECTS["insurance_policy"]["fields"]}
    assert not ({"claim_no", "claim_amount", "preauthorization", "payment", "approved_amount"} & ipf)
    # still pure manifest, no models, no speculative H2 workflows
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("hospital").get_models()) == []


@pytest.mark.django_db
def test_h2_install_provisions_patient_administration(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H2_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for role in ["registration_clerk", "health_information_manager"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="patient_administration_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="patients_report").exists()


@pytest.mark.django_db
def test_h2_patient_is_foundation_with_contacts_and_insurance(template):
    """The patient is the foundational identity every later phase references; contacts and insurance
    coverage link to it (generic *_type metadata carries the variant)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    payer = _rec(ws, member, "payer", {"name": "NHIF", "code": "NHIF",
                                       "payer_type": "government", "status": "active"})
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "Lovelace",
               "gender": "female", "blood_group": "o_pos", "patient_category": "regular",
               "status": "active"})
    kin = _rec(ws, member, "patient_contact", {"patient": str(pat["id"]),
               "contact_type": "next_of_kin", "name": "Byron", "relationship": "Father",
               "is_primary": True})
    pol = _rec(ws, member, "insurance_policy", {"patient": str(pat["id"]),
               "payer": str(payer["id"]), "policy_no": "P-1", "coverage_type": "comprehensive",
               "status": "active"})
    for slug, rid, disc, val in [
        ("patient_contact", kin["id"], "contact_type", "next_of_kin"),
        ("insurance_policy", pol["id"], "coverage_type", "comprehensive"),
    ]:
        ref = _retrieve(ws, member, slug, rid)
        assert str(ref["patient"]) == str(pat["id"]) and ref[disc] == val, slug


@pytest.mark.django_db
def test_h2_patient_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for nm, st in [("A", "active"), ("B", "active"), ("C", "inactive")]:
        _rec(ws, member, "patient", {"first_name": nm, "last_name": "X", "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="active_patients")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_h2_registration_clerk_home_routes(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    clerk = Role.objects.get(workspace_id=ws, slug="registration_clerk")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(clerk.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "patient_administration_dashboard"


# ══ H3 — Scheduling & Appointments ═════════════════════════════════════════════════════════════════
H3_ENTITIES = ["provider_schedule", "appointment", "schedule_exception", "appointment_waitlist"]

# H3 must NOT create derived/clinical entities: no materialized slot, no queue entity, no check-in
# entity, no referral (clinical → H4), no telemedicine_session (→ appointment_type).
# ``referral`` is NOT listed here — it is a legitimate H13 Hospital entity (the durable H-test lesson: a
# forbidden-set lists only permanently-rejected *variants*, NEVER a later-phase entity). At H3 a referral
# was merely out-of-scope for scheduling; H13 owns it (care-transfer request).
_FORBIDDEN_H3_ENTITIES = {"appointment_slot", "slot", "clinic_session", "recurring_schedule",
                          "queue", "opd_queue", "check_in", "checkin",
                          "telemedicine_session", "appointment_note", "availability_exception"}


def test_h3_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h3_scheduling_entities_and_generalization():
    """H3 = 4 scheduling entities; slot/queue/check-in/referral are derived or belong elsewhere.
    appointment_type absorbs telemedicine; provider_schedule.session_type absorbs clinic_session."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H3_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H3_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    at = [f for f in HOSPITAL_OBJECTS["appointment"]["fields"] if f["slug"] == "appointment_type"][0]
    assert "telemedicine" in at["config"]["choices"]                # no telemedicine_session entity
    # check-in is a status + fields on appointment, not an entity
    af = {f["slug"] for f in HOSPITAL_OBJECTS["appointment"]["fields"]}
    assert {"check_in_time", "queue_token", "queue_priority"} <= af  # queue is derived from these
    st = [f for f in HOSPITAL_OBJECTS["appointment"]["fields"] if f["slug"] == "status"][0]
    assert {"confirmed", "checked_in", "waitlisted", "no_show"} <= set(st["config"]["choices"])


@pytest.mark.django_db
def test_h3_install_provisions_scheduling(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H3_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="appointment_eligibility").exists()
    for role in ["appointment_scheduler", "receptionist"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="scheduling_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="appointments_report").exists()


@pytest.mark.django_db
def test_h3_booking_guard_reuses_core_guard_framework(template):
    """The eligibility step is the Core Guard Framework (CG-1) with capacity + availability guards —
    no appointment-specific enforcement engine."""
    from apps.workflows.models import WorkflowDefinition, WorkflowStep
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="appointment_eligibility")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    assert {g["name"] for g in step.config["guards"]} == {"capacity", "provider_available"}


def _sched(ws, member, *, capacity=2):
    fac = _rec(ws, member, "facility", {"name": "F", "code": "F1", "status": "active"})
    prov = _rec(ws, member, "provider", {"name": "Dr X", "provider_type": "physician",
                                         "status": "active"})
    sched = _rec(ws, member, "provider_schedule", {"provider": str(prov["id"]),
                 "facility": str(fac["id"]), "session_type": "opd", "recurrence": "weekly",
                 "day_of_week": "mon", "capacity": capacity, "status": "active"})
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    return {"provider": prov, "schedule": sched, "patient": pat}


def _book(ws, member, ctx, on_commit, *, patient=None, date="2026-02-02"):
    with on_commit(execute=True):
        appt = _rec(ws, member, "appointment", {
            "patient": str((patient or ctx["patient"])["id"]),
            "provider": str(ctx["provider"]["id"]),
            "provider_schedule": str(ctx["schedule"]["id"]),
            "appointment_type": "in_person", "appointment_date": date, "status": "confirmed"})
    return _retrieve(ws, member, "appointment", appt["id"])["status"]


@pytest.mark.django_db
def test_h3_appointment_confirmed_within_capacity(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _sched(ws, member, capacity=2)
    assert _book(ws, member, ctx, django_capture_on_commit_callbacks) == "confirmed"


@pytest.mark.django_db
def test_h3_guard_waitlists_when_session_full(template, django_capture_on_commit_callbacks):
    """A booking beyond provider_schedule.capacity is waitlisted by the UNCHANGED Core Guard —
    availability computed from the schedule, no materialized slot entity."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _sched(ws, member, capacity=1)
    assert _book(ws, member, ctx, django_capture_on_commit_callbacks) == "confirmed"
    other = _rec(ws, member, "patient", {"first_name": "R", "last_name": "S", "status": "active"})
    assert _book(ws, member, ctx, django_capture_on_commit_callbacks, patient=other) == "waitlisted"


@pytest.mark.django_db
def test_h3_guard_waitlists_when_provider_unavailable(
        template, django_capture_on_commit_callbacks):
    """A schedule_exception on the appointment date makes the provider unavailable — the Core Guard
    waitlists the booking (not_exists guard)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _sched(ws, member, capacity=5)
    _rec(ws, member, "schedule_exception", {"provider": str(ctx["provider"]["id"]),
         "exception_type": "leave", "exception_date": "2026-02-02", "status": "active"})
    assert _book(ws, member, ctx, django_capture_on_commit_callbacks, date="2026-02-02") == "waitlisted"


@pytest.mark.django_db
def test_h3_telemedicine_is_appointment_type_metadata(template, django_capture_on_commit_callbacks):
    """A telemedicine visit is the SAME appointment entity + appointment_type metadata — no parallel
    telemedicine model."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _sched(ws, member, capacity=5)
    with django_capture_on_commit_callbacks(execute=True):
        appt = _rec(ws, member, "appointment", {"patient": str(ctx["patient"]["id"]),
                    "provider": str(ctx["provider"]["id"]),
                    "provider_schedule": str(ctx["schedule"]["id"]),
                    "appointment_type": "telemedicine", "appointment_date": "2026-02-03",
                    "status": "confirmed"})
    ref = _retrieve(ws, member, "appointment", appt["id"])
    assert ref["appointment_type"] == "telemedicine" and ref["status"] == "confirmed"


# ══ H4 — Clinical Encounters (EMR) ═════════════════════════════════════════════════════════════════
# History is FOUR distinct entities (user-ratified 2026-07-03: past-medical/surgical/family/social have
# genuinely different structure/lifecycle/reporting/FHIR mapping — NOT a generic clinical_history).
H4_ENTITIES = ["encounter", "clinical_note", "diagnosis", "problem", "allergy", "vital_sign",
               "care_plan", "past_medical_history", "surgical_history", "family_history",
               "social_history"]

# Generalization variants PERMANENTLY rejected (never created by ANY phase): note/exam sub-entities
# (note_type absorbs them) + a generic clinical_history (the four histories are separate). Later-phase
# entities (diagnostic_order H5, prescription H6, admission H7, charge H9) are NOT listed here — they
# are legitimately owned by their phases, which assert their own ownership.
_FORBIDDEN_H4_ENTITIES = {"soap_note", "progress_note", "consultation_note", "operative_note",
                          "physical_exam", "review_of_systems", "clinical_assessment",
                          "chief_complaint", "triage", "clinical_history", "history"}


def test_h4_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h4_clinical_entities_and_generalization():
    """H4 = 11 clinical entities; note/exam variants are note_type metadata; history is FOUR distinct
    entities (no generic clinical_history); no order/prescription/admission/billing (H5/H6/H7/H9).
    allergy now lives here (moved from H2)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H4_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H4_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    nt = [f for f in HOSPITAL_OBJECTS["clinical_note"]["fields"] if f["slug"] == "note_type"][0]
    assert {"soap", "operative", "physical_exam", "review_of_systems"} <= set(nt["config"]["choices"])
    vt = [f for f in HOSPITAL_OBJECTS["vital_sign"]["fields"] if f["slug"] == "vital_type"][0]
    assert {"pulse", "temperature", "spo2"} <= set(vt["config"]["choices"])
    # chief complaint + triage are encounter FIELDS, not entities
    ef = {f["slug"] for f in HOSPITAL_OBJECTS["encounter"]["fields"]}
    assert {"chief_complaint", "triage_level", "encounter_type"} <= ef


def test_h4_history_is_four_distinct_entities_not_generic():
    """The four history entities each carry domain-specific structure the generic model could not
    (surgical→procedure/surgeon; family→relationship; social→usage_status) — clean structured
    reporting for previous-surgeries / family-history / smokers."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "clinical_history" not in HOSPITAL_OBJECTS                       # generic rejected
    assert {"surgeon_name", "procedure_date"} <= {
        f["slug"] for f in HOSPITAL_OBJECTS["surgical_history"]["fields"]}
    assert "relationship" in {f["slug"] for f in HOSPITAL_OBJECTS["family_history"]["fields"]}
    us = [f for f in HOSPITAL_OBJECTS["social_history"]["fields"] if f["slug"] == "usage_status"][0]
    assert {"current", "former", "never"} <= set(us["config"]["choices"])


def test_h4_allergy_moved_from_h2_to_clinical():
    """allergy is a clinical (H4) record linked to the patient — the H2 architectural correction."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    af = {f["slug"] for f in HOSPITAL_OBJECTS["allergy"]["fields"]}
    assert {"patient", "allergen", "allergy_type", "severity"} <= af


@pytest.mark.django_db
def test_h4_install_provisions_clinical_record(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H4_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["encounter_started", "encounter_completed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["physician", "nurse", "medical_director"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="clinical_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="encounters_report").exists()


@pytest.mark.django_db
def test_h4_encounter_owns_the_clinical_record(template):
    """The encounter is the clinical container: notes, diagnoses, problems, allergies, vitals and
    care plans all hang off the patient/encounter (generic *_type carries the variant)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "L", "status": "active"})
    prov = _rec(ws, member, "provider", {"name": "Dr X", "provider_type": "physician",
                                         "status": "active"})
    dx_code = _rec(ws, member, "diagnosis_code", {"code": "J06.9", "description": "URTI",
                   "code_system": "icd10", "status": "active"})
    enc = _rec(ws, member, "encounter", {"patient": str(pat["id"]), "provider": str(prov["id"]),
               "encounter_type": "outpatient", "chief_complaint": "Cough", "status": "planned"})
    note = _rec(ws, member, "clinical_note", {"encounter": str(enc["id"]), "patient": str(pat["id"]),
                "note_type": "soap", "content": "S/O/A/P", "status": "draft"})
    dx = _rec(ws, member, "diagnosis", {"encounter": str(enc["id"]), "patient": str(pat["id"]),
              "diagnosis_code": str(dx_code["id"]), "diagnosis_type": "primary", "status": "active"})
    vit = _rec(ws, member, "vital_sign", {"encounter": str(enc["id"]), "patient": str(pat["id"]),
               "vital_type": "temperature", "value": "38.5", "unit": "C"})
    alg = _rec(ws, member, "allergy", {"patient": str(pat["id"]), "allergen": "Penicillin",
               "allergy_type": "drug", "severity": "severe", "status": "active"})
    assert _retrieve(ws, member, "clinical_note", note["id"])["note_type"] == "soap"
    assert _retrieve(ws, member, "diagnosis", dx["id"])["diagnosis_type"] == "primary"
    assert float(_retrieve(ws, member, "vital_sign", vit["id"])["value"]) == 38.5
    assert _retrieve(ws, member, "allergy", alg["id"])["allergy_type"] == "drug"


@pytest.mark.django_db
def test_h4_encounter_completion_drives_appointment_status(
        template, django_capture_on_commit_callbacks):
    """Completing an encounter closes its H3 appointment (H4 drives the transition; H3 owns the enum)
    — via the frozen Workflow engine, no new engine."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ctx = _sched(ws, member, capacity=5)
    with django_capture_on_commit_callbacks(execute=True):
        appt = _rec(ws, member, "appointment", {"patient": str(ctx["patient"]["id"]),
                    "provider": str(ctx["provider"]["id"]),
                    "provider_schedule": str(ctx["schedule"]["id"]),
                    "appointment_type": "in_person", "appointment_date": "2026-02-05",
                    "status": "confirmed"})
    enc = _rec(ws, member, "encounter", {"patient": str(ctx["patient"]["id"]),
               "provider": str(ctx["provider"]["id"]), "appointment": str(appt["id"]),
               "encounter_type": "outpatient", "status": "planned"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "encounter", enc["id"], {"status": "completed"})
    assert _retrieve(ws, member, "appointment", appt["id"])["status"] == "completed"


@pytest.mark.django_db
def test_h4_clinical_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    for st in ["in_progress", "in_progress", "completed"]:
        _rec(ws, member, "encounter", {"patient": str(pat["id"]), "encounter_type": "outpatient",
                                       "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="open_encounters")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


# ══ H5 — Orders & Results ══════════════════════════════════════════════════════════════════════════
H5_ENTITIES = ["diagnostic_order", "specimen", "diagnostic_result", "result_item"]

# H5 must NOT create lab/imaging-specific order/result entities (order_type/result_type absorb them),
# a panel/test-catalog entity (→ config + service_catalog), or a result_attachment (→ Documents).
_FORBIDDEN_H5_ENTITIES = {"laboratory_order", "imaging_order", "cardiology_order",
                          "laboratory_result", "imaging_result", "blood_specimen", "urine_specimen",
                          "tissue_specimen", "order_panel", "test_catalog", "diagnostic_test",
                          "result_attachment"}


def test_h5_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h5_orders_results_entities_and_generalization():
    """H5 = 4 entities; lab/imaging share one order (order_type) + one result (result_type); specimen
    is generic (specimen_type); panels = config not entities; attachments = Documents platform."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H5_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H5_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    ot = [f for f in HOSPITAL_OBJECTS["diagnostic_order"]["fields"] if f["slug"] == "order_type"][0]
    assert {"laboratory", "imaging", "cardiology"} <= set(ot["config"]["choices"])
    rt = [f for f in HOSPITAL_OBJECTS["diagnostic_result"]["fields"] if f["slug"] == "result_type"][0]
    assert {"laboratory", "imaging"} <= set(rt["config"]["choices"])
    sp = [f for f in HOSPITAL_OBJECTS["specimen"]["fields"] if f["slug"] == "specimen_type"][0]
    assert {"blood", "urine", "tissue"} <= set(sp["config"]["choices"])
    # ordered test references the H1 service catalogue (panel = configuration, not an entity)
    assert any(f["slug"] == "service" and f["config"]["target_entity_slug"] == "service_catalog"
               for f in HOSPITAL_OBJECTS["diagnostic_order"]["fields"])


@pytest.mark.django_db
def test_h5_install_provisions_orders_results(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H5_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["diagnostic_order_placed", "result_released", "specimen_rejected"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["lab_technician", "radiologist"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="diagnostics_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="diagnostic_orders_report").exists()


@pytest.mark.django_db
def test_h5_lab_order_specimen_result_items(template):
    """A lab order → generic specimen + a diagnostic_result with multiple structured result_items
    (FHIR ServiceRequest → Specimen → DiagnosticReport → Observations)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "L", "status": "active"})
    order = _rec(ws, member, "diagnostic_order", {"patient": str(pat["id"]),
                 "order_type": "laboratory", "test_name": "CBC", "priority": "routine",
                 "status": "requested"})
    spec = _rec(ws, member, "specimen", {"diagnostic_order": str(order["id"]),
                "patient": str(pat["id"]), "specimen_type": "blood", "status": "collected"})
    result = _rec(ws, member, "diagnostic_result", {"diagnostic_order": str(order["id"]),
                  "patient": str(pat["id"]), "result_type": "laboratory", "status": "draft"})
    for analyte, val, flag in [("Hemoglobin", "9.1", "low"), ("WBC", "7.5", "normal")]:
        _rec(ws, member, "result_item", {"diagnostic_result": str(result["id"]),
             "analyte": analyte, "value": val, "unit": "g/dL", "abnormal_flag": flag,
             "status": "final"})
    assert _retrieve(ws, member, "specimen", spec["id"])["specimen_type"] == "blood"
    items = RecordService.list_records(
        workspace_id=ws, member=member,
        entity=EntityDefinition.objects.get(workspace_id=ws, slug="result_item"))
    rows = items["results"] if isinstance(items, dict) else items
    assert len([r for r in rows if str(r["diagnostic_result"]) == str(result["id"])]) == 2


@pytest.mark.django_db
def test_h5_imaging_order_needs_no_specimen(template):
    """An imaging order is the SAME diagnostic_order (order_type=imaging) with a narrative report and
    NO specimen — generalization holds (no imaging_order entity)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "Bo", "last_name": "Q", "status": "active"})
    order = _rec(ws, member, "diagnostic_order", {"patient": str(pat["id"]),
                 "order_type": "imaging", "test_name": "Chest X-ray", "status": "requested"})
    result = _rec(ws, member, "diagnostic_result", {"diagnostic_order": str(order["id"]),
                  "patient": str(pat["id"]), "result_type": "imaging",
                  "report": "No acute cardiopulmonary process.", "status": "draft"})
    ref = _retrieve(ws, member, "diagnostic_result", result["id"])
    assert ref["result_type"] == "imaging" and "cardiopulmonary" in ref["report"]


@pytest.mark.django_db
def test_h5_result_release_verifies_order_and_notifies(
        template, django_capture_on_commit_callbacks):
    """Releasing a result marks its order verified (the H5→H4 handoff) via the frozen Workflow
    engine — no new engine."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "R", "status": "active"})
    order = _rec(ws, member, "diagnostic_order", {"patient": str(pat["id"]),
                 "order_type": "laboratory", "status": "in_progress"})
    result = _rec(ws, member, "diagnostic_result", {"diagnostic_order": str(order["id"]),
                  "patient": str(pat["id"]), "result_type": "laboratory", "status": "verified"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "diagnostic_result", result["id"], {"status": "released"})
    assert _retrieve(ws, member, "diagnostic_order", order["id"])["status"] == "verified"


# ══ H6 — Pharmacy & Medication ═════════════════════════════════════════════════════════════════════
H6_ENTITIES = ["prescription", "prescription_item", "medication_dispense",
               "medication_administration", "medication_reconciliation"]

# Permanently-rejected generalization variants (never created by ANY phase): ``medication`` (= the H1
# drug_formulary master — FHIR Medication), ``medication_order`` (= prescription; MedicationRequest
# unifies order + script), the MAR (a derived report over medication_administration), the per-context
# prescription entities (→ prescription_type) and per-route medication entities (→ route metadata).
# NOTE: ``drug_interaction`` is deliberately NOT listed — a future licensed interaction knowledge-base
# reference master is conceivable; only the private CDS *engine* is rejected (safety = Rules/Guard).
_FORBIDDEN_H6_ENTITIES = {"medication", "medication_order", "mar",
                          "medication_administration_record", "inpatient_prescription",
                          "outpatient_prescription", "discharge_prescription", "oral_medication",
                          "iv_medication", "im_medication", "topical_medication", "drug_dispense",
                          "medication_chart"}


def test_h6_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h6_medication_entities_and_generalization():
    """H6 = 5 medication entities; prescription_type unifies inpatient/outpatient/discharge; route is
    metadata; medication = H1 drug_formulary (no new entity); the MAR is a derived report."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H6_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H6_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    pt = [f for f in HOSPITAL_OBJECTS["prescription"]["fields"] if f["slug"] == "prescription_type"][0]
    assert {"inpatient", "outpatient", "discharge"} <= set(pt["config"]["choices"])
    rt = [f for f in HOSPITAL_OBJECTS["prescription_item"]["fields"] if f["slug"] == "route"][0]
    assert {"oral", "iv", "im", "topical"} <= set(rt["config"]["choices"])


def test_h6_medication_maps_to_drug_formulary_not_a_new_entity():
    """CRITICAL governance catch: the drug PRODUCT master is the H1 drug_formulary (FHIR Medication) —
    H6 does NOT create a ``medication`` entity; prescription lines reference drug_formulary."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "medication" not in HOSPITAL_OBJECTS and "drug_formulary" in HOSPITAL_OBJECTS
    for ent in ["prescription_item", "medication_dispense", "medication_administration"]:
        drug = [f for f in HOSPITAL_OBJECTS[ent]["fields"] if f["slug"] == "drug"][0]
        assert drug["config"]["target_entity_slug"] == "drug_formulary", ent


def test_h6_mar_is_a_derived_report_not_an_entity():
    """The Medication Administration Record (MAR) is a REPORT over medication_administration events, not
    a separate entity (the derived-presentation precedent: H3 queue, rejected H2 patient_alert)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "mar" not in HOSPITAL_OBJECTS and "medication_administration_record" not in HOSPITAL_OBJECTS
    assert "medication_administration" in HOSPITAL_OBJECTS       # the atomic event IS an entity
    slugs = {r["slug"] for r in build_hospital_manifest()["reports"]}
    assert "medication_administration_report" in slugs          # the MAR is this report


def test_h6_prescription_unifies_medication_order():
    """prescription IS the medication order (FHIR MedicationRequest) — no separate medication_order
    entity; inpatient vs outpatient is prescription_type metadata."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "medication_order" not in HOSPITAL_OBJECTS
    assert "prescription" in HOSPITAL_OBJECTS
    pf = {f["slug"] for f in HOSPITAL_OBJECTS["prescription"]["fields"]}
    assert "prescription_type" in pf


def test_h6_is_pure_manifest_and_reuses_frozen_executors():
    """H6 adds zero native code; every H6 workflow step reuses a frozen Core executor (drug-safety CDS
    is the Guard Framework, not a private medication engine)."""
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("hospital").get_models()) == []
    allowed = {"action_guard", "action_update_record", "action_send_notification", "condition"}
    h6 = {"prescription_safety_check", "prescription_verified", "medication_dispensed",
          "medication_missed", "medication_reconciliation_completed"}
    wfs = {w["slug"]: w for w in build_hospital_manifest()["workflows"]}
    assert h6 <= set(wfs)
    for slug in h6:
        assert all(s["step_type"] in allowed for s in wfs[slug]["steps"]), slug


@pytest.mark.django_db
def test_h6_install_provisions_pharmacy(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H6_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["prescription_safety_check", "prescription_verified", "medication_dispensed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["pharmacist", "pharmacy_technician"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="pharmacy_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="prescriptions_report").exists()


@pytest.mark.django_db
def test_h6_prescription_with_items_references_formulary(template):
    """A prescription carries drug lines that reference the H1 formulary master (FHIR MedicationRequest
    → dosageInstruction) — no medication entity duplication."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "L", "status": "active"})
    drug = _rec(ws, member, "drug_formulary", {"code": "AMOX500", "name": "Amoxil",
                "generic_name": "Amoxicillin", "form": "capsule", "schedule": "prescription",
                "status": "active"})
    rx = _rec(ws, member, "prescription", {"patient": str(pat["id"]),
              "prescription_type": "outpatient", "priority": "routine", "status": "draft"})
    item = _rec(ws, member, "prescription_item", {"prescription": str(rx["id"]),
                "patient": str(pat["id"]), "drug": str(drug["id"]), "dose": "500", "dose_unit": "mg",
                "route": "oral", "frequency": "TDS", "duration": "5 days", "status": "active"})
    ref = _retrieve(ws, member, "prescription_item", item["id"])
    assert str(ref["drug"]) == str(drug["id"]) and ref["route"] == "oral"
    assert str(ref["prescription"]) == str(rx["id"])


@pytest.mark.django_db
def test_h6_duplicate_therapy_guard_reuses_core_guard_framework(template):
    """Drug-safety is the Core Guard Framework (CG-1) — the safety workflow carries a duplicate_therapy
    guard, no medication-specific CDS engine."""
    from apps.workflows.models import WorkflowStep
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="prescription_safety_check")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    assert {g["name"] for g in step.config["guards"]} == {"duplicate_therapy"}


@pytest.mark.django_db
def test_h6_duplicate_therapy_holds_second_active_item(
        template, django_capture_on_commit_callbacks):
    """The FROZEN Guard flags a second active order for the same patient+drug — the item is held for
    pharmacist review (deterministic CDS, no AI). The first order stays active."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    drug = _rec(ws, member, "drug_formulary", {"code": "WARF", "name": "Warfarin",
                "form": "tablet", "schedule": "prescription", "status": "active"})
    rx = _rec(ws, member, "prescription", {"patient": str(pat["id"]),
              "prescription_type": "inpatient", "status": "signed"})

    def _add_item():
        with django_capture_on_commit_callbacks(execute=True):
            it = _rec(ws, member, "prescription_item", {"prescription": str(rx["id"]),
                      "patient": str(pat["id"]), "drug": str(drug["id"]), "dose": "5",
                      "route": "oral", "status": "active"})
        return _retrieve(ws, member, "prescription_item", it["id"])["status"]

    assert _add_item() == "active"        # first order for the drug — safe
    assert _add_item() == "on_hold"       # duplicate therapy — held by the Core Guard


@pytest.mark.django_db
def test_h6_dispense_drives_prescription_status(template, django_capture_on_commit_callbacks):
    """Dispensing marks the prescription dispensed via the frozen Workflow engine (the H6 pharmacy
    handoff) — no new engine."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "R", "status": "active"})
    drug = _rec(ws, member, "drug_formulary", {"code": "PARA", "name": "Panadol",
                "form": "tablet", "schedule": "otc", "status": "active"})
    rx = _rec(ws, member, "prescription", {"patient": str(pat["id"]),
              "prescription_type": "outpatient", "status": "verified"})
    disp = _rec(ws, member, "medication_dispense", {"prescription": str(rx["id"]),
                "patient": str(pat["id"]), "drug": str(drug["id"]), "quantity_dispensed": "20",
                "batch_no": "LOT-A", "status": "prepared"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "medication_dispense", disp["id"], {"status": "dispensed"})
    assert _retrieve(ws, member, "prescription", rx["id"])["status"] == "dispensed"


@pytest.mark.django_db
def test_h6_dispense_batch_is_reference_not_inventory_recreation():
    """H6 owns clinical dispensing only — the dispense carries a batch REFERENCE string, never stock/
    location/valuation/quantity-on-hand fields (Inventory owns those); no inventory entities recreated."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    df = {f["slug"] for f in HOSPITAL_OBJECTS["medication_dispense"]["fields"]}
    assert "batch_no" in df
    assert not ({"stock_level", "quantity_on_hand", "warehouse", "location", "unit_cost",
                 "valuation", "reorder_level"} & df)
    # H6 recreates none of the Inventory master entities.
    assert not ({"item", "warehouse", "stock_level", "stock_movement", "fifo_layer"}
                & set(HOSPITAL_OBJECTS))


@pytest.mark.django_db
def test_h6_pharmacy_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    for st in ["verified", "verified", "draft"]:
        _rec(ws, member, "prescription", {"patient": str(pat["id"]),
             "prescription_type": "outpatient", "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="prescriptions_to_dispense")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_h6_pharmacist_home_routes(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    pharm = Role.objects.get(workspace_id=ws, slug="pharmacist")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(pharm.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "pharmacy_dashboard"


# ══ H7 — Inpatient, Wards & Nursing ════════════════════════════════════════════════════════════════
H7_ENTITIES = ["admission", "bed_assignment", "transfer", "discharge", "nursing_observation",
               "nursing_task", "nursing_handover", "ward_round"]

# Permanently-rejected variants (never created by ANY phase): the nursing care plan is H4
# care_plan(nursing); the discharge summary + round note are H4 clinical_notes; a bed reservation/hold
# is a bed_assignment in the reserved state (+ H1 bed); bed/ward/room are H1 masters; per-variant
# admission/transfer/round/bed_assignment entities collapse to *_type metadata.
_FORBIDDEN_H7_ENTITIES = {"nursing_care_plan", "discharge_summary", "round_note", "bed_reservation",
                          "bed_hold", "room", "emergency_admission", "elective_admission",
                          "daycare_admission", "icu_transfer", "ward_transfer", "room_transfer",
                          "doctor_round", "nurse_round", "consultant_round", "icu_bed_assignment",
                          "ward_bed_assignment", "isolation_bed_assignment", "inpatient_encounter"}


def test_h7_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h7_inpatient_entities_and_generalization():
    """H7 = 8 inpatient/nursing entities; admission/transfer/round carry *_type metadata; nursing care
    plan / discharge summary / round note / bed reservation are NOT entities (reused or derived)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H7_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H7_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    at = [f for f in HOSPITAL_OBJECTS["admission"]["fields"] if f["slug"] == "admission_type"][0]
    assert {"emergency", "elective", "daycare"} <= set(at["config"]["choices"])
    tt = [f for f in HOSPITAL_OBJECTS["transfer"]["fields"] if f["slug"] == "transfer_type"][0]
    assert {"ward", "icu", "room"} <= set(tt["config"]["choices"])
    rt = [f for f in HOSPITAL_OBJECTS["ward_round"]["fields"] if f["slug"] == "round_type"][0]
    assert {"consultant", "doctor", "nurse"} <= set(rt["config"]["choices"])
    # a bed reservation/hold is the reserved state of a bed_assignment, not an entity
    bs = [f for f in HOSPITAL_OBJECTS["bed_assignment"]["fields"] if f["slug"] == "status"][0]
    assert "reserved" in set(bs["config"]["choices"])


def test_h7_admission_is_distinct_from_encounter():
    """The admission is the inpatient EPISODE (references its admitting H4 encounter) — NOT the visit;
    no inpatient_encounter entity, encounter stays H4."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "inpatient_encounter" not in HOSPITAL_OBJECTS and "encounter" in HOSPITAL_OBJECTS
    af = {f["slug"] for f in HOSPITAL_OBJECTS["admission"]["fields"]}
    assert "encounter" in af and "admission_type" in af          # links the visit, owns the episode


def test_h7_bed_assignment_owns_occupancy_not_the_bed_master():
    """H1 owns the bed master; H7 owns only the assignment/occupancy lifecycle. H7 recreates NO
    bed/ward/room/facility master — bed_assignment references the H1 bed + ward."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    # bed/ward/facility are the SAME H1 masters (not re-declared by H7); room is never an entity
    assert "room" not in HOSPITAL_OBJECTS
    bed = [f for f in HOSPITAL_OBJECTS["bed_assignment"]["fields"] if f["slug"] == "bed"][0]
    assert bed["config"]["target_entity_slug"] == "bed"          # references H1 master
    st = [f for f in HOSPITAL_OBJECTS["bed_assignment"]["fields"] if f["slug"] == "status"][0]
    assert {"assigned", "occupied", "released"} <= set(st["config"]["choices"])


def test_h7_nursing_observation_does_not_duplicate_vital_sign():
    """Nursing observation owns NON-vital assessments; vitals stay the H4 vital_sign primitive (no
    BP/pulse/temp choices duplicated here). The nursing care plan is H4 care_plan(nursing)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    ot = [f for f in HOSPITAL_OBJECTS["nursing_observation"]["fields"]
          if f["slug"] == "observation_type"][0]["config"]["choices"]
    assert {"intake_output", "wound_assessment", "mobility"} <= set(ot)
    assert not ({"blood_pressure_systolic", "pulse", "temperature", "spo2"} & set(ot))  # vitals = H4
    assert "nursing_care_plan" not in HOSPITAL_OBJECTS           # = H4 care_plan(care_plan_type=nursing)
    assert "nursing" in [f for f in HOSPITAL_OBJECTS["care_plan"]["fields"]
                         if f["slug"] == "care_plan_type"][0]["config"]["choices"]


def test_h7_discharge_summary_is_h4_clinical_note_not_an_h7_entity():
    """H7 owns the discharge PROCESS/event; the discharge SUMMARY is an H4 clinical_note(note_type=
    discharge) — reused, not recreated."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "discharge" in HOSPITAL_OBJECTS and "discharge_summary" not in HOSPITAL_OBJECTS
    assert "discharge" in [f for f in HOSPITAL_OBJECTS["clinical_note"]["fields"]
                          if f["slug"] == "note_type"][0]["config"]["choices"]


def test_h7_is_pure_manifest_and_reuses_frozen_executors():
    """H7 adds zero native code; every H7 workflow step reuses a frozen Core executor (bed availability
    is the Guard Framework, not a private bed engine)."""
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("hospital").get_models()) == []
    allowed = {"action_guard", "action_update_record", "action_send_notification", "condition"}
    h7 = {"bed_assignment_check", "bed_occupied", "bed_released", "admission_admitted",
          "transfer_completed", "discharge_completed"}
    wfs = {w["slug"]: w for w in build_hospital_manifest()["workflows"]}
    assert h7 <= set(wfs)
    for slug in h7:
        assert all(s["step_type"] in allowed for s in wfs[slug]["steps"]), slug


@pytest.mark.django_db
def test_h7_install_provisions_inpatient(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H7_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["bed_assignment_check", "bed_occupied", "discharge_completed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["bed_manager", "ward_clerk"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="inpatient_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="admissions_report").exists()


@pytest.mark.django_db
def test_h7_admission_bed_assignment_flow(template):
    """Admit a patient into an H1 ward/bed and assign the bed — the assignment references the H1 bed
    master (not a recreated bed) and owns its own occupancy status."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    fac = _rec(ws, member, "facility", {"name": "CH", "code": "CH", "status": "active"})
    ward = _rec(ws, member, "ward", {"name": "Ward A", "code": "WA", "ward_type": "general",
                                     "facility": str(fac["id"]), "status": "active"})
    bed = _rec(ws, member, "bed", {"label": "A-1", "bed_type": "general", "ward": str(ward["id"]),
                                   "status": "available"})
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "L", "status": "active"})
    adm = _rec(ws, member, "admission", {"patient": str(pat["id"]), "ward": str(ward["id"]),
               "admission_type": "elective", "status": "admitted"})
    asg = _rec(ws, member, "bed_assignment", {"admission": str(adm["id"]), "patient": str(pat["id"]),
               "bed": str(bed["id"]), "ward": str(ward["id"]), "status": "assigned"})
    ref = _retrieve(ws, member, "bed_assignment", asg["id"])
    assert str(ref["bed"]) == str(bed["id"]) and str(ref["admission"]) == str(adm["id"])
    assert ref["status"] == "assigned"


@pytest.mark.django_db
def test_h7_bed_availability_guard_reuses_core_guard_framework(template):
    """The bed-assignment eligibility step is the Core Guard Framework (CG-1) with a bed_available
    guard — no bed-specific enforcement engine."""
    from apps.workflows.models import WorkflowStep
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="bed_assignment_check")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    assert {g["name"] for g in step.config["guards"]} == {"bed_available"}


@pytest.mark.django_db
def test_h7_bed_occupancy_drives_h1_bed_status(template, django_capture_on_commit_callbacks):
    """Occupying a bed_assignment drives the H1 bed master to occupied and releasing frees it — H7 owns
    occupancy, H1 owns the bed, wired via the frozen Workflow engine (H7→H1 handoff)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    ward = _rec(ws, member, "ward", {"name": "W", "code": "W1", "status": "active"})
    bed = _rec(ws, member, "bed", {"label": "B-1", "ward": str(ward["id"]), "status": "available"})
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    adm = _rec(ws, member, "admission", {"patient": str(pat["id"]), "status": "admitted"})
    asg = _rec(ws, member, "bed_assignment", {"admission": str(adm["id"]), "patient": str(pat["id"]),
               "bed": str(bed["id"]), "status": "assigned"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "bed_assignment", asg["id"], {"status": "occupied"})
    assert _retrieve(ws, member, "bed", bed["id"])["status"] == "occupied"
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "bed_assignment", asg["id"], {"status": "released"})
    assert _retrieve(ws, member, "bed", bed["id"])["status"] == "available"


@pytest.mark.django_db
def test_h7_discharge_closes_admission(template, django_capture_on_commit_callbacks):
    """Completing a discharge closes its admission (H7 discharge → admission handoff) via the frozen
    Workflow engine — no new engine."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "R", "status": "active"})
    adm = _rec(ws, member, "admission", {"patient": str(pat["id"]), "status": "admitted"})
    dis = _rec(ws, member, "discharge", {"admission": str(adm["id"]), "patient": str(pat["id"]),
               "discharge_type": "routine", "status": "approved"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "discharge", dis["id"], {"status": "discharged"})
    assert _retrieve(ws, member, "admission", adm["id"])["status"] == "discharged"


@pytest.mark.django_db
def test_h7_inpatient_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    for st in ["admitted", "admitted", "discharged"]:
        _rec(ws, member, "admission", {"patient": str(pat["id"]), "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="current_inpatients")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_h7_bed_manager_home_routes(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    bm = Role.objects.get(workspace_id=ws, slug="bed_manager")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(bm.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "inpatient_dashboard"


# ══ H8 — Surgery / OT & Critical Care ══════════════════════════════════════════════════════════════
H8_ENTITIES = ["operating_theatre", "ot_schedule", "surgery", "surgical_procedure",
               "anaesthesia_record", "surgical_team_member", "surgical_checklist", "icu_episode",
               "icu_observation", "recovery_episode", "implant", "implant_usage"]

# Permanently-rejected variants: surgical_team (= its members) / procedure_participant (= team_member);
# ventilator_setting/event (→ icu_observation.observation_type); per-variant surgery/anaesthesia/icu/
# implant entities (→ *_type metadata). NOTE: clinical_resource is deliberately NOT built yet (specific
# operating_theatre now; generalize on evidence). ``transfusion``/``blood_unit`` are NOT listed here —
# they are legitimate H10 Blood Bank entities (the durable H-test lesson: a forbidden-set lists only
# permanently-rejected variants, NEVER later-phase entities); ``blood_transfusion`` stays (a never-built
# variant name → the H10 ``transfusion``).
_FORBIDDEN_H8_ENTITIES = {"surgical_team", "procedure_participant", "ventilator_setting",
                          "ventilator_event", "blood_transfusion",
                          "major_surgery", "minor_surgery", "emergency_surgery", "elective_surgery",
                          "general_anaesthesia", "regional_anaesthesia", "sedation_record",
                          "nicu", "picu", "ccu", "prosthesis", "stent", "mesh"}


def test_h8_manifest_validates_clean():
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h8_surgical_entities_and_generalization():
    """H8 = 12 perioperative/critical-care entities; procedure/anaesthesia/icu/implant carry *_type
    metadata; team/procedure lines + implant usage are first-class relationship entities."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert set(H8_ENTITIES) <= set(HOSPITAL_OBJECTS)
    assert _FORBIDDEN_H8_ENTITIES.isdisjoint(HOSPITAL_OBJECTS)
    pt = [f for f in HOSPITAL_OBJECTS["surgery"]["fields"] if f["slug"] == "procedure_type"][0]
    assert {"major", "minor"} <= set(pt["config"]["choices"])
    at = [f for f in HOSPITAL_OBJECTS["anaesthesia_record"]["fields"]
          if f["slug"] == "anaesthesia_type"][0]
    assert {"general", "regional", "local", "sedation"} <= set(at["config"]["choices"])
    it = [f for f in HOSPITAL_OBJECTS["icu_episode"]["fields"] if f["slug"] == "icu_type"][0]
    assert {"icu", "nicu", "picu", "ccu"} <= set(it["config"]["choices"])
    mt = [f for f in HOSPITAL_OBJECTS["implant"]["fields"] if f["slug"] == "implant_type"][0]
    assert {"prosthesis", "mesh", "stent"} <= set(mt["config"]["choices"])


def test_h8_surgery_references_encounter_not_duplicates_it():
    """The surgery is the surgical CASE referencing its H4 encounter — it does not duplicate the visit;
    procedures performed are a first-class surgical_procedure child (FHIR Procedure)."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    sf = {f["slug"] for f in HOSPITAL_OBJECTS["surgery"]["fields"]}
    assert "encounter" in sf and "procedure_type" in sf
    enc = [f for f in HOSPITAL_OBJECTS["surgery"]["fields"] if f["slug"] == "encounter"][0]
    assert enc["config"]["target_entity_slug"] == "encounter"    # references H4
    assert "surgical_procedure" in HOSPITAL_OBJECTS              # coded procedures = a child entity


def test_h8_surgical_team_is_a_first_class_relationship_entity():
    """The Global Relationship Review outcome: the surgical team is an ASSIGNMENT entity (role +
    multiplicity + status for relief), NOT a lookup — no surgical_team header / procedure_participant."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "surgical_team" not in HOSPITAL_OBJECTS and "procedure_participant" not in HOSPITAL_OBJECTS
    tm = {f["slug"] for f in HOSPITAL_OBJECTS["surgical_team_member"]["fields"]}
    assert {"surgery", "provider", "team_role", "status"} <= tm     # role + status = a real assignment
    st = [f for f in HOSPITAL_OBJECTS["surgical_team_member"]["fields"] if f["slug"] == "status"][0]
    assert "relieved" in set(st["config"]["choices"])               # temporary/relief-capable


def test_h8_icu_owns_episode_not_admission_and_no_vital_duplication():
    """ICU owns the intensive-care EPISODE (references the H7 admission); icu_observation owns ICU-
    specific params (ventilator/haemodynamic) — vitals stay the H4 vital_sign primitive."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    adm = [f for f in HOSPITAL_OBJECTS["icu_episode"]["fields"] if f["slug"] == "admission"][0]
    assert adm["config"]["target_entity_slug"] == "admission"    # references H7, does not recreate
    ot = [f for f in HOSPITAL_OBJECTS["icu_observation"]["fields"]
          if f["slug"] == "observation_type"][0]["config"]["choices"]
    assert {"ventilator_mode", "map", "gcs"} <= set(ot)          # ICU-specific
    assert not ({"blood_pressure_systolic", "pulse", "temperature"} & set(ot))  # vitals = H4
    assert "ventilator_setting" not in HOSPITAL_OBJECTS         # ventilator = observation_type


def test_h8_transfusion_and_blood_unit_belong_to_blood_bank_not_h8():
    """Blood/transfusion boundary held: the crossmatch→issue→transfuse lifecycle is owned by the H10
    Blood Bank (``transfusion``/``blood_unit`` now exist as H10 entities), and H10 REFERENCES the H8
    surgery (H10 → H8), never the reverse. No ``blood_transfusion`` variant was ever built."""
    from apps.hospital.blueprint import HOSPITAL_OBJECTS
    assert "blood_transfusion" not in HOSPITAL_OBJECTS                 # rejected variant → transfusion
    assert {"transfusion", "blood_unit"} <= set(HOSPITAL_OBJECTS)      # owned by H10 Blood Bank
    # the boundary direction: the H10 blood_request references the H8 surgery (peri-operative transfusion).
    br = {f["slug"]: f for f in HOSPITAL_OBJECTS["blood_request"]["fields"]}
    assert br["surgery"]["config"]["target_entity_slug"] == "surgery"


def test_h8_is_pure_manifest_and_reuses_frozen_executors():
    from django.apps import apps as dj_apps
    assert list(dj_apps.get_app_config("hospital").get_models()) == []
    allowed = {"action_guard", "action_update_record", "action_send_notification", "condition"}
    h8 = {"surgery_booking_check", "theatre_occupied", "theatre_released", "surgery_completed",
          "icu_stepped_down", "recovery_ready"}
    wfs = {w["slug"]: w for w in build_hospital_manifest()["workflows"]}
    assert h8 <= set(wfs)
    for slug in h8:
        assert all(s["step_type"] in allowed for s in wfs[slug]["steps"]), slug


@pytest.mark.django_db
def test_h8_install_provisions_surgery(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in H8_ENTITIES:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["surgery_booking_check", "theatre_occupied", "surgery_completed"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    for role in ["surgeon", "anaesthetist", "ot_coordinator", "scrub_nurse", "intensivist"]:
        assert Role.objects.filter(workspace_id=ws, slug=role).exists(), role
    assert Dashboard.objects.filter(workspace_id=ws, slug="surgery_dashboard").exists()
    assert Report.objects.filter(workspace_id=ws, slug="surgeries_report").exists()


@pytest.mark.django_db
def test_h8_surgery_case_with_procedures_and_team(template):
    """A surgery references the H4 encounter and carries coded procedures + a multi-member team
    (first-class relationship rows) + implant traceability."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "Ada", "last_name": "L", "status": "active"})
    prov = _rec(ws, member, "provider", {"name": "Dr Cut", "provider_type": "surgeon",
                                         "status": "active"})
    enc = _rec(ws, member, "encounter", {"patient": str(pat["id"]), "encounter_type": "inpatient",
                                         "status": "in_progress"})
    px = _rec(ws, member, "procedure_code", {"code": "44970", "description": "Lap appendectomy",
              "code_system": "cpt", "status": "active"})
    sx = _rec(ws, member, "surgery", {"patient": str(pat["id"]), "encounter": str(enc["id"]),
              "surgeon": str(prov["id"]), "procedure_type": "major", "urgency": "emergency",
              "status": "booked"})
    proc = _rec(ws, member, "surgical_procedure", {"surgery": str(sx["id"]),
                "patient": str(pat["id"]), "procedure_code": str(px["id"]), "name": "Appendectomy",
                "sequence": 1, "status": "planned"})
    tm = _rec(ws, member, "surgical_team_member", {"surgery": str(sx["id"]),
              "provider": str(prov["id"]), "team_role": "lead_surgeon", "is_lead": True,
              "status": "assigned"})
    assert str(_retrieve(ws, member, "surgery", sx["id"])["encounter"]) == str(enc["id"])
    assert _retrieve(ws, member, "surgical_procedure", proc["id"])["sequence"] == 1
    assert _retrieve(ws, member, "surgical_team_member", tm["id"])["team_role"] == "lead_surgeon"


@pytest.mark.django_db
def test_h8_theatre_capacity_guard_reuses_core_guard_framework(template):
    """The surgery booking step is the Core Guard Framework (CG-1) with a theatre_capacity guard — no
    surgery-specific enforcement engine (mirrors the H3 appointment capacity guard)."""
    from apps.workflows.models import WorkflowStep
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="surgery_booking_check")
    step = WorkflowStep.objects.get(workspace_id=ws, workflow_id=wf.id, step_type="action_guard")
    assert {g["name"] for g in step.config["guards"]} == {"theatre_capacity"}


@pytest.mark.django_db
def test_h8_theatre_capacity_guard_blocks_overbooking(
        template, django_capture_on_commit_callbacks):
    """A booking beyond the theatre-session capacity is flagged by the UNCHANGED Core Guard (dynamic
    threshold from ot_schedule.capacity) — the first booking passes, the second conflicts."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    theatre = _rec(ws, member, "operating_theatre", {"name": "OT-1", "code": "OT1",
                   "theatre_type": "general", "status": "available"})
    sess = _rec(ws, member, "ot_schedule", {"operating_theatre": str(theatre["id"]),
                "session_type": "elective", "capacity": 1, "status": "active"})
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})

    def _book():
        with django_capture_on_commit_callbacks(execute=True):
            _rec(ws, member, "surgery", {"patient": str(pat["id"]),
                 "ot_schedule": str(sess["id"]), "operating_theatre": str(theatre["id"]),
                 "procedure_type": "minor", "status": "booked"})
        from apps.guards.services import GuardService
        return GuardService.evaluate(workspace_id=ws, guards=[{
            "name": "theatre_capacity",
            "query": {"entity": "surgery", "filter": {"op": "and", "conditions": [
                {"field": "ot_schedule", "op": "=", "value": str(sess["id"])},
                {"field": "status", "op": "=", "value": "booked"}]}},
            "aggregate": "count", "operator": "lte", "threshold": 1, "severity": "block"}],
            emit=False).passed

    _book()
    assert _book() is False        # the 2nd booking exceeds capacity=1 → guard fails


@pytest.mark.django_db
def test_h8_theatre_occupancy_driven_by_surgery_lifecycle(
        template, django_capture_on_commit_callbacks):
    """Moving a surgery in_theatre marks its theatre occupied; closing it releases the theatre to
    cleaning — the surgery lifecycle drives the H8 theatre status via the frozen Workflow engine."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    theatre = _rec(ws, member, "operating_theatre", {"name": "OT-2", "code": "OT2",
                   "status": "available"})
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "R", "status": "active"})
    sx = _rec(ws, member, "surgery", {"patient": str(pat["id"]),
              "operating_theatre": str(theatre["id"]), "procedure_type": "major", "status": "prepared"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "surgery", sx["id"], {"status": "in_theatre"})
    assert _retrieve(ws, member, "operating_theatre", theatre["id"])["status"] == "occupied"
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "surgery", sx["id"], {"status": "closed"})
    assert _retrieve(ws, member, "operating_theatre", theatre["id"])["status"] == "cleaning"


@pytest.mark.django_db
def test_h8_icu_episode_references_admission(template):
    """An ICU episode is the critical-care stay WITHIN an H7 admission (icu_type metadata) — it
    references the admission, it does not recreate it."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "S", "status": "active"})
    adm = _rec(ws, member, "admission", {"patient": str(pat["id"]), "status": "admitted"})
    icu = _rec(ws, member, "icu_episode", {"patient": str(pat["id"]), "admission": str(adm["id"]),
               "icu_type": "icu", "reason": "post_operative", "status": "active"})
    ref = _retrieve(ws, member, "icu_episode", icu["id"])
    assert str(ref["admission"]) == str(adm["id"]) and ref["icu_type"] == "icu"


@pytest.mark.django_db
def test_h8_surgery_kpi_evaluates_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    for st in ["completed", "completed", "booked"]:
        _rec(ws, member, "surgery", {"patient": str(pat["id"]), "procedure_type": "minor",
                                     "status": st})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="completed_surgeries")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_h8_surgeon_home_routes(template):
    from apps.studio.services import resolve_home_layout
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    surg = Role.objects.get(workspace_id=ws, slug="surgeon")
    layout = resolve_home_layout(workspace_id=ws, role_ids=[str(surg.id)])
    assert layout is not None and layout.scope == "role"
    assert layout.widgets[0]["config"]["dashboard_slug"] == "surgery_dashboard"
