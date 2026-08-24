"""
Hospital H12 — Patient Portal · Executive Analytics certification.

The leanest phase: **ZERO new business entities.** H12 reuses the FROZEN Portal Platform (row-isolated
`portal_grants`) + Analytics/Dashboards (executive scorecards) — the certified University U8 portals
pattern. Validates: no new entities (count unchanged), portal grants installed as PortalEntityGrant
(link_field=patient), the FROZEN PortalDataService row-isolation (a patient sees only their own rows) +
create forcing the patient link (no spoofing), executive dashboards + role, and cross-module KPI reuse.
"""
import uuid

import pytest
from django.contrib.auth.hashers import make_password

from apps.hospital.blueprint import build_hospital_manifest, seed_hospital_template
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.portal.data_services import PortalDataService
from apps.portal.models import PortalEntityGrant, PortalUser
from apps.records.services import RecordService
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member

# H12 adds NO entities. Proven WITHOUT pinning an absolute total (that would couple this test to every
# future phase — the durable H-test lesson): H12 introduces NONE of the portal/executive candidate
# entities, and delivers its function purely as `portal_grants` config (see the tests below).
_FORBIDDEN_H12_ENTITIES = {
    "portal_message", "patient_portal_account", "portal_access", "patient_portal",  # → Portal Platform
    "executive_report", "scorecard", "board_pack",                                  # → Reporting/Analytics
}


@pytest.fixture
def template(db):
    return seed_hospital_template()


def _rec(ws, member, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=member, entity=entity, data=data)


# ── zero new entities / manifest ──────────────────────────────────────────────
def test_h12_manifest_validates_clean():
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(build_hospital_manifest()) == []


def test_h12_adds_no_new_entities():
    """H12 is pure config (portal grants + executive dashboards) — it adds ZERO business entities."""
    m = build_hospital_manifest()
    slugs = {e["slug"] for e in m["entities"]}
    # H12 delivers its function via portal_grants config, NOT entities — none of the portal/exec
    # candidate entities exist; and H12 declared portal_grants (the config that IS H12's payload).
    assert _FORBIDDEN_H12_ENTITIES.isdisjoint(slugs)
    assert m["portal_grants"]


def test_h12_portal_grants_in_manifest():
    """Every portal grant is a patient-scoped access declaration (link_field=patient) over an EXISTING
    entity — the patient realm, not a new data store."""
    grants = build_hospital_manifest()["portal_grants"]
    by_entity = {g["entity_slug"]: g for g in grants}
    assert {"encounter", "diagnostic_result", "prescription", "invoice"} <= set(by_entity)
    assert all(g["portal_type"] == "patient" and g["link_field"] == "patient" for g in grants)
    # patients may REQUEST appointments and SUBMIT complaints (create), everything else read-only.
    assert by_entity["appointment"]["can_create"] and by_entity["complaint"]["can_create"]
    assert not by_entity["invoice"]["can_create"]


# ── provisioning ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_h12_install_provisions_portal_grants_and_executive(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ("encounter", "diagnostic_result", "prescription", "invoice", "appointment",
                 "complaint"):
        assert PortalEntityGrant.objects.filter(
            workspace_id=ws, entity_slug=slug, portal_type="patient").exists(), slug
    from apps.reporting.models import Dashboard
    for dash in ("executive_overview_dashboard", "executive_quality_safety_dashboard"):
        assert Dashboard.objects.filter(workspace_id=ws, slug=dash).exists(), dash
    assert Role.objects.filter(workspace_id=ws, slug="hospital_executive").exists()


# ── frozen Portal Platform row-isolation (behavior) ───────────────────────────
def _portal_user(ws, patient_id, email):
    return PortalUser.objects.create(
        workspace_id=ws, email=email, full_name="P", password_hash=make_password("Str0ng!pw"),
        is_active=True, is_verified=True, linked_record_id=patient_id, portal_type="patient")


@pytest.mark.django_db
def test_h12_patient_portal_sees_only_own_records(template):
    """The FROZEN PortalDataService AND-injects patient = linked_record_id — a patient can never reach
    another patient's rows (unspoofable, server-side). H12 only declares the grant; isolation is reused."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat_a = _rec(ws, member, "patient", {"first_name": "A", "last_name": "A", "status": "active"})
    pat_b = _rec(ws, member, "patient", {"first_name": "B", "last_name": "B", "status": "active"})
    # invoices for each patient (no workflow side effects on invoice draft create).
    _rec(ws, member, "invoice", {"patient": str(pat_a["id"]), "invoice_type": "outpatient",
                                 "total_amount": "100.00", "status": "draft"})
    _rec(ws, member, "invoice", {"patient": str(pat_b["id"]), "invoice_type": "outpatient",
                                 "total_amount": "200.00", "status": "draft"})
    user_a = _portal_user(ws, pat_a["id"], "a@pt.com")
    rows = PortalDataService.list_records(user_a, "invoice")
    assert len(rows) == 1 and str(rows[0]["patient"]) == str(pat_a["id"])


@pytest.mark.django_db
def test_h12_portal_create_forces_patient_link(template):
    """A portal-created complaint is forced onto the portal user's own patient — a client-supplied
    patient (spoof attempt) is overridden server-side."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat_a = _rec(ws, member, "patient", {"first_name": "A", "last_name": "A", "status": "active"})
    pat_b = _rec(ws, member, "patient", {"first_name": "B", "last_name": "B", "status": "active"})
    user_a = _portal_user(ws, pat_a["id"], "a2@pt.com")
    created = PortalDataService.create_record(
        user_a, "complaint",
        {"complaint_type": "service", "description": "X", "status": "received",
         "patient": str(pat_b["id"])})            # spoof attempt → overridden
    assert str(created["patient"]) == str(pat_a["id"])


@pytest.mark.django_db
def test_h12_ungranted_entity_denied_to_portal(template):
    """A portal user cannot reach an entity that was NOT granted to the patient realm (e.g. incident)."""
    from apps.portal.data_services import PortalAccessError
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "A", "last_name": "A", "status": "active"})
    user = _portal_user(ws, pat["id"], "a3@pt.com")
    with pytest.raises(PortalAccessError):
        PortalDataService.list_records(user, "incident")


# ── executive analytics reuse ─────────────────────────────────────────────────
@pytest.mark.django_db
def test_h12_executive_reuses_cross_module_kpis(template):
    """Executive dashboards surface EXISTING H1–H11 KPIs across modules (no new analytics/entities)."""
    from apps.analytics.models import KPIDefinition
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for code in ("current_inpatients", "total_surgeries", "total_incidents", "units_available"):
        assert KPIDefinition.objects.filter(workspace_id=ws, code=code).exists(), code
