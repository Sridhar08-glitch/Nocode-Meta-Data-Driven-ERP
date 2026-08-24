"""
Hospital H11 — Quality · Accreditation · Patient Safety certification.

Pure manifest over the FROZEN cross-cutting platforms — Analytics KPI / Reporting / Dashboards /
**Rules (block_save)** / **SLA** / Workflow / Notifications / Documents / Audit. `apps/hospital` stays
model-less; H11 adds metadata entities + Rules/SLA config only (the certified University U9 / College C9
pattern). Validates: entity presence + generalization (incident/audit/capa/complaint/standard variants →
*_type metadata; no quality-indicator/policy/per-variant entities), rules + SLA installed & reused (no new
validation framework), incident workflow + severe-escalation, SLA auto-attach, block_save integrity
(risk-score bound + CAPA effectiveness), the audit→finding→CAPA chain, accreditation lifecycle, quality
roles, and an operational KPI.
"""
import uuid

import pytest

from apps.hospital.blueprint import build_hospital_manifest, seed_hospital_template
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member


@pytest.fixture
def template(db):
    return seed_hospital_template()


H11_ENTITIES = ["incident", "capa", "accreditation", "quality_standard", "quality_audit",
                "audit_finding", "complaint", "risk_assessment"]

# Only PERMANENTLY-rejected variants/duplications (never-created) — NOT later-phase entities.
_FORBIDDEN_H11_ENTITIES = {
    "quality_indicator", "quality_measure", "core_measure",   # → Analytics KPI Library
    "policy", "sop", "controlled_document",                   # → Documents platform
    "accreditation_body",                                     # → body_type metadata
    "sentinel_event", "near_miss", "medication_error",        # → incident_type + flags
    "corrective_action", "preventive_action",                 # → capa_type
    "rca", "root_cause_analysis", "investigation",            # → incident investigation fields/status
    "grievance", "patient_feedback",                          # → complaint_type
    "compliance_requirement", "compliance_record",            # → quality_standard + audit_finding
    "hand_hygiene_audit", "eoc_round",                        # → quality_audit(audit_type)
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
def test_h11_entities_installed(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    slugs = set(EntityDefinition.objects.filter(workspace_id=ws).values_list("slug", flat=True))
    assert set(H11_ENTITIES) <= slugs
    assert _FORBIDDEN_H11_ENTITIES.isdisjoint(slugs)


def test_h11_manifest_validates_clean():
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h11_only_adds_rules_and_sla_reusing_engines():
    """H11 adds the `rules` + `sla_policies` manifest sections reusing the generic Rules/SLA engines —
    every rule is a block_save guard (no new validation framework); Hospital stays model-less."""
    m = build_hospital_manifest()
    assert m["rules"] and m["sla_policies"]
    assert all(a["type"] == "block_save" for r in m["rules"] for a in r["actions"])


def test_h11_generalization_no_per_variant_entities():
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    it = next(f for f in objs["incident"]["fields"] if f["slug"] == "incident_type")
    assert {"fall", "medication_error", "hai", "wrong_site"} <= set(it["config"]["choices"])
    at = next(f for f in objs["quality_audit"]["fields"] if f["slug"] == "audit_type")
    assert {"accreditation_survey", "hand_hygiene", "environment_of_care"} <= set(at["config"]["choices"])
    ct = next(f for f in objs["capa"]["fields"] if f["slug"] == "capa_type")
    assert {"corrective", "preventive"} <= set(ct["config"]["choices"])
    assert _FORBIDDEN_H11_ENTITIES.isdisjoint(set(objs))


def test_h11_sentinel_and_rca_are_metadata_not_entities():
    """A sentinel event is an incident FLAG (not an entity); the RCA is the incident's investigation
    fields+status (not a separate investigation entity)."""
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    fslugs = {f["slug"] for f in objs["incident"]["fields"]}
    assert {"is_sentinel", "is_near_miss", "root_cause", "investigation_summary"} <= fslugs
    assert "sentinel_event" not in objs and "rca" not in objs and "investigation" not in objs


# ── rules + SLA reuse (the frozen engines) ────────────────────────────────────
@pytest.mark.django_db
def test_h11_install_provisions_rules_and_sla(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    from apps.rules.models import BusinessRule
    from apps.sla.models import SLAPolicy
    assert BusinessRule.objects.filter(
        workspace_id=ws, slug="validate_risk_assessment_risk_score_before_create").exists()
    assert BusinessRule.objects.filter(workspace_id=ws, slug="validate_capa_closure").exists()
    for pol in ["incident_investigation_sla", "capa_completion_sla", "complaint_resolution_sla"]:
        assert SLAPolicy.objects.filter(workspace_id=ws, slug=pol).exists(), pol


@pytest.mark.django_db
def test_h11_rule_blocks_out_of_range_risk_score(template):
    """A risk score beyond the 5×5 matrix is rejected by the frozen Rules engine (block_save)."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with pytest.raises(RuleBlocked):
        _rec(ws, member, "risk_assessment", {"title": "Bad", "risk_score": 30, "status": "assessed"})
    ok = _rec(ws, member, "risk_assessment", {"title": "Good", "risk_score": 12, "status": "assessed"})
    assert ok["id"]


@pytest.mark.django_db
def test_h11_rule_blocks_capa_verify_without_completion(template):
    """A CAPA cannot be marked verified until a completion date is recorded (closure integrity) — a
    representation-robust block_save rule (the str-based Rules engine can't reliably compare booleans)."""
    from apps.rules.services import RuleBlocked
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    capa = _rec(ws, member, "capa", {"capa_type": "corrective", "title": "Fix", "status": "open"})
    with pytest.raises(RuleBlocked):
        _update(ws, member, "capa", capa["id"], {"status": "verified"})
    # once a completion date is recorded, verification is allowed.
    _update(ws, member, "capa", capa["id"], {"completed_date": "2026-07-06", "status": "verified"})
    assert _retrieve(ws, member, "capa", capa["id"])["status"] == "verified"


@pytest.mark.django_db
def test_h11_sla_attaches_on_incident_create(template, django_capture_on_commit_callbacks):
    """A patient-safety incident auto-attaches its SLA (the frozen SLA engine) on creation."""
    from apps.sla.models import SLARecord
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        inc = _rec(ws, member, "incident", {"incident_type": "fall", "severity": "moderate",
                                            "status": "reported"})
    assert SLARecord.objects.filter(workspace_id=ws, record_id=inc["id"]).exists()


# ── workflows ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_h11_incident_reported_workflow_escalates_severe(template,
                                                         django_capture_on_commit_callbacks):
    """A reported incident fires the workflow; a severe event runs the escalation branch to completion."""
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "incident", {"incident_type": "wrong_site", "severity": "catastrophic",
                                      "is_sentinel": True, "status": "reported"})
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="incident_reported")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id,
                                      status="completed").exists()


@pytest.mark.django_db
def test_h11_accreditation_granted_workflow(template, django_capture_on_commit_callbacks):
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        acr = _rec(ws, member, "accreditation", {"name": "JCI 2026", "body_type": "jci",
                                                 "status": "surveyed"})
        _update(ws, member, "accreditation", acr["id"], {"status": "accredited"})
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="accreditation_granted")
    assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id,
                                      status="completed").exists()


# ── traceability + roles + KPI ────────────────────────────────────────────────
@pytest.mark.django_db
def test_h11_audit_finding_capa_chain(template):
    """audit → finding (against a standard) → CAPA is a queryable reference chain (no lineage engine)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    std = _rec(ws, member, "quality_standard", {"standard_code": "IPSG.1", "title": "Identify patients",
               "source_type": "accreditation", "standard_type": "standard", "status": "active"})
    aud = _rec(ws, member, "quality_audit", {"name": "Mock Survey", "audit_type": "mock_survey",
                                             "status": "completed"})
    fnd = _rec(ws, member, "audit_finding", {"quality_audit": str(aud["id"]),
               "quality_standard": str(std["id"]), "compliance": "non_compliant", "severity": "major",
               "status": "open"})
    capa = _rec(ws, member, "capa", {"capa_type": "corrective", "title": "Wristband policy",
                                     "audit_finding": str(fnd["id"]), "status": "open"})
    fnd_r = _retrieve(ws, member, "audit_finding", fnd["id"])
    assert str(fnd_r["quality_audit"]) == str(aud["id"])
    assert str(fnd_r["quality_standard"]) == str(std["id"])
    assert str(_retrieve(ws, member, "capa", capa["id"])["audit_finding"]) == str(fnd["id"])


@pytest.mark.django_db
def test_h11_quality_roles_present(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ("quality_manager", "patient_safety_officer", "accreditation_coordinator",
                 "risk_manager", "compliance_officer"):
        assert Role.objects.filter(workspace_id=ws, slug=slug).exists(), slug


@pytest.mark.django_db
def test_h11_operational_kpi_via_analytics(template):
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for _ in range(2):
        _rec(ws, member, "capa", {"capa_type": "corrective", "title": "X", "status": "open"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="open_capas")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2
