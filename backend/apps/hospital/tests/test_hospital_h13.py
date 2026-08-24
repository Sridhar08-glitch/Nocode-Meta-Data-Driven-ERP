"""
Hospital H13 — FINAL functional phase (Consent · Referral · HIM/ROI · CSSD · Dietary · Transport ·
Mortuary) certification.

Pure manifest over the FROZEN platforms: 8 genuine Hospital business objects + reuse of Workflow / Rules
(block_save) / SLA / Documents / Portal / Analytics / Assets / Inventory / Audit. `apps/hospital` stays
model-less. Validates: entity presence + generalization (no per-variant/duplicated entities), IPC
isolation REUSES H4 care_plan (no isolation entity), the CSSD pass→sterile workflow, closure-integrity
Rules (death release / ROI disclosure — representation-robust `is null`), SLA auto-attach, a referral
workflow, ownership (no platform leak), roles, and an operational KPI.
"""
import uuid

import pytest

from apps.hospital.blueprint import build_hospital_manifest, seed_hospital_template
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member

H13_ENTITIES = ["consent", "referral", "medical_record_request", "instrument_set",
                "sterilization_cycle", "diet_order", "transport_request", "death_record"]

# Only PERMANENTLY-rejected variants/duplications (never-created) — NOT later-phase entities.
_FORBIDDEN_H13_ENTITIES = {
    "isolation_precaution",                                  # → H4 care_plan(care_plan_type=isolation)
    "surgery_consent", "transfusion_consent",               # → consent(consent_type)
    "referral_completion", "referral_feedback",             # → referral status + feedback field
    "amendment_request", "disclosure_log",                  # → medical_record_request(request_type)
    "autoclave_load", "sterile_pack",                       # → cycle_type / Inventory
    "therapeutic_diet", "meal", "ward_meal", "meal_tray",   # → diet_type / Inventory + task
    "ot_transport", "radiology_transport",                  # → transport_request(purpose)
    "body_custody", "body_release",                         # → death_record status + fields
    "outbreak", "surveillance",                             # → H11 incident/risk + Analytics
}


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


# ── architecture / generalization / ownership ─────────────────────────────────
@pytest.mark.django_db
def test_h13_entities_installed(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    slugs = set(EntityDefinition.objects.filter(workspace_id=ws).values_list("slug", flat=True))
    assert set(H13_ENTITIES) <= slugs
    assert _FORBIDDEN_H13_ENTITIES.isdisjoint(slugs)


def test_h13_manifest_validates_clean():
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h13_generalization_no_per_variant_entities():
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    ct = next(f for f in objs["consent"]["fields"] if f["slug"] == "consent_type")
    assert {"treatment", "surgery", "transfusion", "dnr"} <= set(ct["config"]["choices"])
    dt = next(f for f in objs["diet_order"]["fields"] if f["slug"] == "diet_type")
    assert {"regular", "diabetic", "npo", "enteral"} <= set(dt["config"]["choices"])
    assert _FORBIDDEN_H13_ENTITIES.isdisjoint(set(objs))


def test_h13_isolation_reuses_care_plan_not_a_new_entity():
    """IPC isolation is H4 care_plan(care_plan_type=isolation) — NOT an isolation_precaution entity."""
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    assert "isolation_precaution" not in objs
    cpt = next(f for f in objs["care_plan"]["fields"] if f["slug"] == "care_plan_type")
    assert "isolation" in cpt["config"]["choices"]


def test_h13_no_ownership_leak():
    """Hospital owns the business record; equipment→Assets, consumables→Inventory, money→Finance.
    Instrument sets reference the Assets register; diet orders reference the H4 allergy."""
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    iset = {f["slug"]: f for f in objs["instrument_set"]["fields"]}
    assert iset["asset_ref"]["config"]["target_entity_slug"] == "asset"          # Assets, not duplicated
    cyc = {f["slug"]: f for f in objs["sterilization_cycle"]["fields"]}
    assert cyc["sterilizer_asset"]["config"]["target_entity_slug"] == "asset"
    diet = {f["slug"]: f for f in objs["diet_order"]["fields"]}
    assert diet["allergy"]["config"]["target_entity_slug"] == "allergy"          # H4, not re-modeled
    slugs = {e["slug"] for e in objs.values()}
    assert {"gl_entry", "journal", "sterile_pack", "meal"}.isdisjoint(slugs)      # no platform leak


# ── CSSD workflow (pass → sterile) ────────────────────────────────────────────
@pytest.mark.django_db
def test_h13_sterilization_pass_marks_set_sterile(template, django_capture_on_commit_callbacks):
    """A PASSED sterilization cycle marks the linked instrument set sterile (OT traceability chain)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    iset = _rec(ws, member, "instrument_set", {"name": "Ortho Tray", "set_type": "orthopedic",
                                               "status": "in_cycle"})
    cyc = _rec(ws, member, "sterilization_cycle", {"cycle_type": "steam",
               "instrument_set": str(iset["id"]), "bio_indicator": "pass", "status": "loaded"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "sterilization_cycle", cyc["id"], {"status": "passed"})
    assert _retrieve(ws, member, "instrument_set", iset["id"])["status"] == "sterile"


# ── closure-integrity Rules (block_save; representation-robust) ───────────────
@pytest.mark.django_db
def test_h13_install_provisions_rules_and_sla(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.rules.models import BusinessRule
    from apps.sla.models import SLAPolicy
    for slug in ("validate_death_release", "validate_record_disclosure", "validate_consent_active"):
        assert BusinessRule.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for pol in ("referral_response_sla", "transport_turnaround_sla", "roi_turnaround_sla"):
        assert SLAPolicy.objects.filter(workspace_id=ws, slug=pol).exists(), pol


@pytest.mark.django_db
def test_h13_rule_blocks_death_release_without_date(template):
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "A", "last_name": "A", "status": "active"})
    dr = _rec(ws, member, "death_record", {"patient": str(pat["id"]), "manner": "natural",
                                           "status": "recorded"})
    with pytest.raises(RuleBlocked):
        _update(ws, member, "death_record", dr["id"], {"status": "released"})
    _update(ws, member, "death_record", dr["id"], {"release_date": "2026-07-06", "status": "released"})
    assert _retrieve(ws, member, "death_record", dr["id"])["status"] == "released"


@pytest.mark.django_db
def test_h13_rule_blocks_roi_release_without_recipient(template):
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "B", "last_name": "B", "status": "active"})
    req = _rec(ws, member, "medical_record_request", {"patient": str(pat["id"]), "request_type": "roi",
               "requester_type": "patient", "status": "in_review"})
    with pytest.raises(RuleBlocked):
        _update(ws, member, "medical_record_request", req["id"], {"status": "released"})
    _update(ws, member, "medical_record_request", req["id"],
            {"disclosed_to": "Patient", "status": "released"})
    assert _retrieve(ws, member, "medical_record_request", req["id"])["status"] == "released"


@pytest.mark.django_db
def test_h13_sla_attaches_on_transport_request(template, django_capture_on_commit_callbacks):
    from apps.sla.models import SLARecord
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "C", "last_name": "C", "status": "active"})
    with django_capture_on_commit_callbacks(execute=True):
        tr = _rec(ws, member, "transport_request", {"patient": str(pat["id"]),
                  "transport_type": "wheelchair", "purpose": "radiology", "priority": "routine",
                  "status": "requested"})
    assert SLARecord.objects.filter(workspace_id=ws, record_id=tr["id"]).exists()


# ── workflow + roles + KPI ────────────────────────────────────────────────────
@pytest.mark.django_db
def test_h13_referral_completed_workflow(template, django_capture_on_commit_callbacks):
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        ref = _rec(ws, member, "referral", {"referral_type": "internal", "priority": "routine",
                                            "status": "sent"})
        _update(ws, member, "referral", ref["id"], {"status": "completed", "feedback": "seen"})
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="referral_completed")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id,
                                      status="completed").exists()


@pytest.mark.django_db
def test_h13_roles_present(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ("medical_records_officer", "referral_coordinator", "cssd_technician", "dietitian",
                 "transport_coordinator", "mortuary_officer"):
        assert Role.objects.filter(workspace_id=ws, slug=slug).exists(), slug


@pytest.mark.django_db
def test_h13_operational_kpi_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for _ in range(2):
        _rec(ws, member, "diet_order", {"diet_type": "diabetic", "status": "active"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="active_diet_orders")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.fixture
def template(db):
    return seed_hospital_template()
