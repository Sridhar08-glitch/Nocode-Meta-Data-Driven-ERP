"""
Hospital H9 — Billing certification (thin: clinical charge capture + claim lifecycle).

Every money movement goes through the FROZEN Finance Platform via reused workflow executors
(action_post_journal → GLBus, action_register_settlement_document / action_auto_allocate /
action_auto_reconcile → Settlement). Hospital ships ZERO ledger/tax/settlement code (pure manifest).
Validates: entity presence + generalization (no per-variant / duplicated-finance entities), payer
reuse (H1, not recreated), invoice→GL, invoice→Settlement, payment→GL, claim→Notification, an
OPERATIONAL KPI (financial ratios stay in F13), and billing roles.
"""
import uuid

import pytest

from apps.hospital.blueprint import build_hospital_manifest, seed_hospital_template
from apps.ledger.models import JournalEntry
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.records.services import RecordService
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member


@pytest.fixture
def template(db):
    return seed_hospital_template()


H9_ENTITIES = ["charge", "invoice", "claim", "claim_line", "preauthorization", "remittance", "payment"]

_FORBIDDEN_H9_ENTITIES = {
    "outpatient_invoice", "inpatient_invoice",        # → invoice(invoice_type)
    "insurance_payment", "cash_payment",              # → payment(payment_method)
    "invoice_line",                                   # → a charge references its invoice (IS the line)
    "coverage",                                       # → H2 insurance_policy owns coverage
    "gl_entry", "journal", "ledger_account",          # → Finance Platform (GL), never in Hospital
    "tax_code", "settlement_document", "receivable",  # → Finance Platform, never in Hospital
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


@pytest.mark.django_db
def test_h9_entities_installed(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    slugs = set(EntityDefinition.objects.filter(workspace_id=ws).values_list("slug", flat=True))
    assert set(H9_ENTITIES) <= slugs
    assert _FORBIDDEN_H9_ENTITIES.isdisjoint(slugs)


@pytest.mark.django_db
def test_h9_reuses_h1_payer_not_a_new_one(template):
    """H9 references the H1 payer master — it does NOT recreate payer (no duplication)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="payer").count() == 1
    invoice = next(e for e in build_hospital_manifest()["entities"] if e["slug"] == "invoice")
    inv_fields = {f["slug"] for f in invoice["fields"]}
    assert "payer" in inv_fields                      # invoice references the H1 payer via lookup


@pytest.mark.django_db
def test_h9_generalization_metadata(template):
    """invoice_type is metadata (not outpatient_invoice/inpatient_invoice entities)."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "P", "last_name": "Q", "status": "active"})
    inv = _rec(ws, member, "invoice", {"patient": str(pat["id"]), "invoice_type": "inpatient",
                                       "total_amount": "100.00", "status": "draft"})
    assert _retrieve(ws, member, "invoice", inv["id"])["invoice_type"] == "inpatient"


@pytest.mark.django_db
def test_h9_invoice_finalize_posts_gl_via_finance_platform(template,
                                                           django_capture_on_commit_callbacks):
    """KEY reuse: finalizing an invoice posts through the FROZEN GLBus (Dr A/R 1100 / Cr Service
    Revenue 4100). Hospital ships no ledger; the entry is posted by the Finance Platform."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "A", "last_name": "B", "status": "active"})
    with django_capture_on_commit_callbacks(execute=True):
        inv = _rec(ws, member, "invoice", {"patient": str(pat["id"]), "invoice_type": "outpatient",
                                           "total_amount": "500.00", "status": "draft"})
    assert JournalEntry.objects.filter(workspace_id=ws, source_module="hospital").count() == 0
    with django_capture_on_commit_callbacks(execute=True):
        _update(ws, member, "invoice", inv["id"], {"status": "finalized"})
    entries = JournalEntry.objects.filter(workspace_id=ws, source_module="hospital")
    assert entries.count() == 1
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entries.first().lines.all()}
    assert lines["1100"][0] == 500 and lines["4100"][1] == 500


@pytest.mark.django_db
def test_h9_invoice_registers_settlement_document(template, django_capture_on_commit_callbacks):
    """Invoice finalization registers an A/R document in the FROZEN Settlement engine (aging +
    matching) — Hospital owns no settlement/allocation logic."""
    from apps.settlement.models import SettlementDocument
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "C", "last_name": "D", "status": "active"})
    with django_capture_on_commit_callbacks(execute=True):
        inv = _rec(ws, member, "invoice", {"patient": str(pat["id"]), "invoice_type": "outpatient",
                                           "total_amount": "300.00", "status": "draft"})
        _update(ws, member, "invoice", inv["id"], {"status": "finalized"})
    assert SettlementDocument.objects.filter(workspace_id=ws, doc_type="invoice").exists()


@pytest.mark.django_db
def test_h9_payment_posts_cash_via_finance_platform(template, django_capture_on_commit_callbacks):
    """A payment posts cash through GLBus (Dr Cash 1000 / Cr A/R 1100) — reused Finance Platform."""
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    pat = _rec(ws, member, "patient", {"first_name": "E", "last_name": "F", "status": "active"})
    with django_capture_on_commit_callbacks(execute=True):
        _rec(ws, member, "payment", {"patient": str(pat["id"]), "payment_method": "cash",
                                     "amount": "200.00", "status": "received"})
    entries = JournalEntry.objects.filter(workspace_id=ws, source_module="hospital")
    assert entries.count() == 1
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entries.first().lines.all()}
    assert lines["1000"][0] == 200 and lines["1100"][1] == 200


@pytest.mark.django_db
def test_h9_claim_submitted_fires_workflow(template, django_capture_on_commit_callbacks):
    """Submitting a claim fires the claim_submitted workflow (reusing the frozen Workflow engine);
    the workflow runs to completion. (Actual notification delivery depends on a configured recipient
    — the point here is that Hospital ships NO workflow/notification engine, only manifest config.)"""
    from apps.workflows.models import WorkflowDefinition, WorkflowRun
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    with django_capture_on_commit_callbacks(execute=True):
        clm = _rec(ws, member, "claim", {"claim_type": "professional", "claimed_amount": "400.00",
                                         "status": "draft"})
        _update(ws, member, "claim", clm["id"], {"status": "submitted"})
    wf = WorkflowDefinition.objects.get(workspace_id=ws, slug="claim_submitted")
    runs = WorkflowRun.objects.filter(workspace_id=ws, workflow_id=wf.id)
    assert runs.exists() and runs.filter(status="completed").exists()


@pytest.mark.django_db
def test_h9_billing_kpi_is_operational_not_a_finance_ratio(template):
    """H9 KPIs are OPERATIONAL counts via the frozen Analytics engine; revenue-cycle financial
    ratios live in the F13 Financial KPI Library, never duplicated here (KPI governance)."""
    from apps.analytics.models import KPIDefinition
    from apps.analytics.services import KPIService
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    member = system_member(None)
    for _ in range(2):
        _rec(ws, member, "claim", {"claim_type": "professional", "status": "submitted"})
    kpi = KPIDefinition.objects.get(workspace_id=ws, code="pending_claims")
    assert int(float(KPIService.evaluate(workspace_id=ws, kpi=kpi)["value"])) == 2


@pytest.mark.django_db
def test_h9_billing_roles_present(template):
    ws = uuid.uuid4()
    sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    for slug in ("billing_clerk", "claims_officer", "billing_manager"):
        assert Role.objects.filter(workspace_id=ws, slug=slug).exists()
