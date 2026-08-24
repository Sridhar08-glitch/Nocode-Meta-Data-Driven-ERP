"""
Hospital H10 — Blood Bank / Transfusion Medicine certification.

Pure manifest over the FROZEN Core: metadata entities + the Guard Framework (blood-safety gates) +
Workflow/Notifications + append-only Audit (vein-to-vein traceability). Hospital ships ZERO native code.
Validates: entity presence + generalization (component/test/donation/issue/reaction variants → *_type,
no per-variant entities; no duplicated Inventory/Finance entities), the SERIALIZED blood_unit (NOT an
Inventory stock row — the H8 implant precedent), Assets reference for storage, the unit-release safety
guard (reactive test → re-quarantine), crossmatch → reservation, the routine-issue compatibility gate
(block) + emergency uncrossmatched override (warn, audited), transfusion consumption, haemovigilance
(reaction/recall/storage-excursion workflows), full vein-to-vein traceability, an OPERATIONAL KPI, and
the blood-bank roles. Money never moves here (transfusions bill via the H9 charge → Finance Platform).
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


H10_ENTITIES = ["donor", "donation", "blood_unit", "blood_test", "crossmatch", "blood_request",
                "blood_issue", "transfusion", "transfusion_reaction", "blood_recall",
                "storage_excursion"]

# Only PERMANENTLY-rejected generalization/duplication variants (never-created) — NOT later-phase
# entities (the durable H-test lesson). Each is a *_type metadata value, a status, a derived view, or
# owned by a frozen platform (Inventory/Finance).
_FORBIDDEN_H10_ENTITIES = {
    "blood_component",                                  # → component_type on blood_unit
    "blood_inventory",                                  # → derived over status + Inventory reagents
    "blood_screening", "infectious_disease_test", "blood_grouping",  # → test_type on blood_test
    "compatibility",                                    # → crossmatch.compatibility (result field)
    "reservation",                                      # → blood_unit reserved status
    "discard",                                          # → blood_unit discarded status + reason
    "traceability",                                     # → derived report/graph over the FK chain
    "blood_stock", "blood_item",                        # → Inventory (fungible reagents), never here
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
def test_h10_entities_installed(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    slugs = set(EntityDefinition.objects.filter(workspace_id=ws).values_list("slug", flat=True))
    assert set(H10_ENTITIES) <= slugs
    assert _FORBIDDEN_H10_ENTITIES.isdisjoint(slugs)


def test_h10_manifest_validates_clean():
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h10_generalization_no_per_variant_entities():
    """component/test/donation/issue/reaction variants are *_type metadata — no per-variant entities."""
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    unit_types = next(f for f in objs["blood_unit"]["fields"] if f["slug"] == "component_type")
    assert {"whole_blood", "prbc", "ffp", "platelets"} <= set(unit_types["config"]["choices"])
    test_types = next(f for f in objs["blood_test"]["fields"] if f["slug"] == "test_type")
    assert {"abo_rh_grouping", "antibody_screen", "infectious_disease"} <= set(
        test_types["config"]["choices"])
    assert _FORBIDDEN_H10_ENTITIES.isdisjoint(set(objs))


def test_h10_blood_unit_is_serialized_clinical_object_not_inventory():
    """A blood_unit is a SERIALIZED clinical entity (own id + component + expiry + status lifecycle) —
    NOT an Inventory stock row (the H8 implant precedent). Inventory is reused only for fungible reagents."""
    objs = {e["slug"]: e for e in build_hospital_manifest()["entities"]}
    unit = objs["blood_unit"]
    fslugs = {f["slug"]: f for f in unit["fields"]}
    assert "unit_no" in fslugs and fslugs["unit_no"]["field_type"] == "auto_number"   # serialized id
    assert "expiry_date" in fslugs and "component_type" in fslugs and "status" in fslugs
    # storage equipment is REFERENCED from the Assets platform, not owned/duplicated by Blood Bank.
    assert fslugs["storage_asset"]["config"]["target_entity_slug"] == "asset"


def test_h10_no_finance_entities_billing_reuses_h9_charge():
    """Blood Bank owns NO ledger/tax/settlement/invoice entity; a transfusion is billed via the H9
    charge (present) — money moves only through the Finance Platform."""
    slugs = {e["slug"] for e in build_hospital_manifest()["entities"]}
    assert {"gl_entry", "journal", "blood_charge", "blood_invoice"}.isdisjoint(slugs)
    assert "charge" in slugs and "invoice" in slugs      # the H9 (reused) billing entities


# ── blood-safety guards (Core Guard Framework, CG-1) ──────────────────────────
def _unit(ws, member, *, status="quarantine", group="o_neg"):
    don = _rec(ws, member, "donation", {"donation_type": "whole_blood", "status": "collected"})
    return _rec(ws, member, "blood_unit", {"donation": str(don["id"]), "component_type": "prbc",
                                           "blood_group": group, "status": status})


@pytest.mark.django_db
def test_h10_unit_release_blocked_by_reactive_test(template, django_capture_on_commit_callbacks):
    """A unit with a REACTIVE qualification test cannot be released — the Guard reverts it to quarantine
    (the certified optimistic-create/false-branch-correct pattern)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    unit = _unit(ws, member, status="quarantine")
    _rec(ws, member, "blood_test", {"blood_unit": str(unit["id"]), "test_type": "infectious_disease",
                                    "subject_type": "unit", "result": "reactive", "status": "resulted"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "blood_unit", unit["id"], {"status": "available"})
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "quarantine"


@pytest.mark.django_db
def test_h10_unit_release_succeeds_when_no_reactive_test(template,
                                                         django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    unit = _unit(ws, member, status="quarantine")
    _rec(ws, member, "blood_test", {"blood_unit": str(unit["id"]), "test_type": "abo_rh_grouping",
                                    "subject_type": "unit", "result": "non_reactive",
                                    "status": "verified"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "blood_unit", unit["id"], {"status": "available"})
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "available"


@pytest.mark.django_db
def test_h10_crossmatch_compatible_reserves_unit(template, django_capture_on_commit_callbacks):
    """A COMPATIBLE crossmatch reserves the unit for the recipient (reservation = state, not entity)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "A", "last_name": "B", "status": "active"})
    unit = _unit(ws, member, status="available")
    req = _rec(ws, member, "blood_request", {"patient": str(pat["id"]), "component_type": "prbc",
                                             "blood_group": "o_neg", "request_type": "routine",
                                             "status": "crossmatching"})
    xm = _rec(ws, member, "crossmatch", {"blood_request": str(req["id"]),
                                         "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                                         "method": "serologic", "compatibility": "incompatible",
                                         "status": "pending"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "crossmatch", xm["id"], {"compatibility": "compatible",
                                                     "status": "complete"})
    ref = _retrieve(ws, member, "blood_unit", unit["id"])
    assert ref["status"] == "reserved" and str(ref["reserved_for"]) == str(pat["id"])


def _issue_ctx(ws, member, *, compatible):
    pat = _rec(ws, member, "patient", {"first_name": "C", "last_name": "D", "status": "active"})
    unit = _unit(ws, member, status="reserved")
    req = _rec(ws, member, "blood_request", {"patient": str(pat["id"]), "component_type": "prbc",
                                             "blood_group": "o_neg", "request_type": "routine",
                                             "status": "ready"})
    if compatible:
        _rec(ws, member, "crossmatch", {"blood_request": str(req["id"]),
                                        "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                                        "method": "serologic", "compatibility": "compatible",
                                        "status": "complete"})
    return pat, unit, req


@pytest.mark.django_db
def test_h10_routine_issue_blocked_without_compatible_crossmatch(
        template, django_capture_on_commit_callbacks):
    """The SAFETY GATE: a routine issue is BLOCKED (rejected) when no compatible crossmatch exists."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat, unit, req = _issue_ctx(ws, member, compatible=False)
    with django_capture_on_commit_callbacks(execute=True):
        iss = _rec(ws, member, "blood_issue", {"blood_request": str(req["id"]),
                   "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                   "issue_type": "routine", "status": "issued"})
    assert _retrieve(ws, member, "blood_issue", iss["id"])["status"] == "rejected"
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "reserved"   # not issued


@pytest.mark.django_db
def test_h10_routine_issue_succeeds_with_compatible_crossmatch(
        template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat, unit, req = _issue_ctx(ws, member, compatible=True)
    with django_capture_on_commit_callbacks(execute=True):
        iss = _rec(ws, member, "blood_issue", {"blood_request": str(req["id"]),
                   "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                   "issue_type": "routine", "status": "issued"})
    assert _retrieve(ws, member, "blood_issue", iss["id"])["status"] == "issued"
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "issued"


@pytest.mark.django_db
def test_h10_emergency_uncrossmatched_issue_overrides_with_audit(
        template, django_capture_on_commit_callbacks):
    """Emergency uncrossmatched release: the SAME guard runs at WARN severity (never blocking); the unit
    is issued despite no crossmatch, and the authorized override is recorded (audited)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat, unit, req = _issue_ctx(ws, member, compatible=False)
    authorizer = str(uuid.uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        iss = _rec(ws, member, "blood_issue", {"blood_request": str(req["id"]),
                   "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                   "issue_type": "emergency", "is_emergency": True, "authorized_by": authorizer,
                   "override_reason": "Massive transfusion protocol — O-neg", "status": "issued"})
    ref = _retrieve(ws, member, "blood_issue", iss["id"])
    assert ref["status"] == "issued"                                         # NOT blocked
    assert str(ref["authorized_by"]) == authorizer and ref["override_reason"]
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "issued"


@pytest.mark.django_db
def test_h10_transfusion_completion_consumes_unit(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "E", "last_name": "F", "status": "active"})
    unit = _unit(ws, member, status="issued")
    tx = _rec(ws, member, "transfusion", {"blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                                          "status": "started"})
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "transfusion", tx["id"], {"status": "completed"})
    assert _retrieve(ws, member, "blood_unit", unit["id"])["status"] == "transfused"


@pytest.mark.django_db
def test_h10_transfusion_reaction_flags_transfusion(template, django_capture_on_commit_callbacks):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "G", "last_name": "H", "status": "active"})
    unit = _unit(ws, member, status="transfused")
    tx = _rec(ws, member, "transfusion", {"blood_unit": str(unit["id"]), "patient": str(pat["id"]),
                                          "status": "started"})
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "transfusion_reaction", {"transfusion": str(tx["id"]),
             "blood_unit": str(unit["id"]), "patient": str(pat["id"]),
             "reaction_type": "acute_hemolytic", "severity": "severe", "status": "reported"})
    assert _retrieve(ws, member, "transfusion", tx["id"])["status"] == "reaction"


@pytest.mark.django_db
def test_h10_haemovigilance_workflows_fire(template, django_capture_on_commit_callbacks):
    """Storage excursion + blood recall fire their Core workflows to completion (regulated events)."""
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "storage_excursion", {"storage_location": "Fridge A", "severity": "critical",
                                               "disposition": "pending", "status": "open"})
        _rec(ws, member, "blood_recall", {"reason": "donor_positive_test", "status": "initiated"})
    for slug in ("storage_excursion_reported", "blood_recall_initiated"):
        wf = WorkflowDefinition.objects.get(workspace_id=ws, slug=slug)
        assert WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id,
                                          status="completed").exists(), slug


# ── traceability (vein-to-vein) + roles + KPI ─────────────────────────────────
@pytest.mark.django_db
def test_h10_vein_to_vein_traceability_chain(template):
    """The full donor → donation → unit → crossmatch → issue → transfusion → recipient FK chain is
    queryable in BOTH directions (the derived traceability graph; no duplicate lineage engine)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "R", "last_name": "X", "status": "active"})
    donor = _rec(ws, member, "donor", {"name": "Donor One", "donor_type": "voluntary",
                                       "blood_group": "o_neg", "status": "active"})
    don = _rec(ws, member, "donation", {"donor": str(donor["id"]), "donation_type": "whole_blood",
                                        "status": "released"})
    unit = _rec(ws, member, "blood_unit", {"donation": str(don["id"]), "component_type": "prbc",
                                           "blood_group": "o_neg", "status": "available"})
    req = _rec(ws, member, "blood_request", {"patient": str(pat["id"]), "component_type": "prbc",
                                             "blood_group": "o_neg", "request_type": "routine",
                                             "status": "ready"})
    xm = _rec(ws, member, "crossmatch", {"blood_request": str(req["id"]), "blood_unit": str(unit["id"]),
                                         "patient": str(pat["id"]), "compatibility": "compatible",
                                         "status": "complete"})
    iss = _rec(ws, member, "blood_issue", {"blood_request": str(req["id"]),
               "blood_unit": str(unit["id"]), "crossmatch": str(xm["id"]), "patient": str(pat["id"]),
               "issue_type": "routine", "status": "issued"})
    tx = _rec(ws, member, "transfusion", {"blood_issue": str(iss["id"]), "blood_unit": str(unit["id"]),
                                          "patient": str(pat["id"]), "status": "completed"})
    # backward (recipient reaction → source donor): transfusion → unit → donation → donor
    tx_r = _retrieve(ws, member, "transfusion", tx["id"])
    unit_r = _retrieve(ws, member, "blood_unit", tx_r["blood_unit"])
    don_r = _retrieve(ws, member, "donation", unit_r["donation"])
    assert str(_retrieve(ws, member, "donation", don_r["id"])["donor"]) == str(donor["id"])
    # forward (donor recall → recipient): the issue+transfusion tie the unit to the recipient
    assert str(tx_r["patient"]) == str(pat["id"]) and str(tx_r["blood_issue"]) == str(iss["id"])


@pytest.mark.django_db
def test_h10_blood_bank_roles_present(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ("blood_bank_manager", "donor_coordinator", "blood_bank_technologist",
                 "haemovigilance_officer"):
        assert Role.objects.filter(workspace_id=ws, slug=slug).exists(), slug


@pytest.mark.django_db
def test_h10_operational_kpi_via_analytics(template):
    """H10 KPIs are OPERATIONAL counts via the frozen Analytics engine (no financial ratios here)."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for _ in range(3):
        _unit(ws, member, status="available")
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="units_available")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 3
