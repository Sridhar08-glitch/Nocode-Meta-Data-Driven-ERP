"""
P2.15 ERP-readiness remediation certification (PROJECT_HANDBOOK.md "P2.15 REMEDIATION PHASE").

Proves the five blockers are closed:
  1. Accounting auto-provisioning   — fresh workspace posts with zero manual setup
  2. Manufacturing account mappings — WIP/FG accounts exist + post
  3. Silent GL failures removed     — failures raise + emit a ledger.post.failed audit event
  4. Asset disposal idempotency     — dispose twice ⇒ one disposal + one journal
  5. Project cost idempotency       — post twice ⇒ one cost entry, correct actual_cost

Everything reuses the existing engines (GLBus / InventoryService / AssetService / projects).
Backend-agnostic: runs identically on SQLite and PostgreSQL.
"""
import datetime
import uuid

import pytest

from apps.eventstore.models import DomainEvent
from apps.ledger.models import AccountingSettings, JournalEntry, LedgerAccount, PostingRule
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus, LedgerError, emit_post_failure

A = str(uuid.uuid4())


# ── Blocker 1 — accounting auto-provisioning + completeness ──────────────────
@pytest.mark.django_db
def test_provision_seeds_chart_settings_and_rules():
    ws = uuid.uuid4()
    result = provision_accounting(ws)
    assert result["accounts_created"] > 0
    # Standard chart present, including the previously-missing WIP/FG/accum-depr accounts.
    for code in ("1000", "1200", "1400", "1500", "1600", "1700", "2000", "2050", "5000", "6300"):
        assert LedgerAccount.objects.filter(workspace_id=ws, code=code).exists(), code
    assert AccountingSettings.objects.filter(workspace_id=ws).exists()
    for event_type in ("inventory.received", "inventory.issued", "vendor_bill.posted"):
        assert PostingRule.objects.filter(
            workspace_id=ws, event_type=event_type, is_active=True).exists(), event_type


@pytest.mark.django_db
def test_provision_is_idempotent():
    ws = uuid.uuid4()
    provision_accounting(ws)
    second = provision_accounting(ws)
    assert second["accounts_created"] == 0 and second["posting_rules_created"] == 0
    assert AccountingSettings.objects.filter(workspace_id=ws).count() == 1


@pytest.mark.django_db
def test_install_provisions_accounting():
    """Installing any solution makes the workspace ready to post — no manual API calls."""
    from apps.crm.blueprint import seed_crm_template
    from apps.solution_templates import services as st

    ws = uuid.uuid4()
    st.install(template_id=seed_crm_template().id, workspace_id=ws, installed_by=None)
    assert LedgerAccount.objects.filter(workspace_id=ws).exists()
    assert AccountingSettings.objects.filter(workspace_id=ws).exists()
    assert PostingRule.objects.filter(workspace_id=ws, event_type="inventory.received").exists()


@pytest.mark.django_db
def test_fresh_workspace_inventory_transaction_creates_journal():
    """Blocker-1 acceptance: Fresh workspace → provision → inventory txn → Journal Created."""
    from apps.inventory.models import Item, Warehouse
    from apps.inventory.services import InventoryService

    ws = uuid.uuid4()
    provision_accounting(ws)
    item = Item.objects.create(workspace_id=ws, sku="WIDGET", name="Widget",
                               valuation_method="average")
    wh = Warehouse.objects.create(workspace_id=ws, code="MAIN", name="Main")

    mv = InventoryService.receive(ws, item.id, wh.id, 10, "5", reference="GRN-1", actor_id=A)
    assert mv.journal_entry_id is not None
    je = JournalEntry.objects.get(workspace_id=ws, id=mv.journal_entry_id)
    assert je.status == "posted" and je.source_module == "inventory"
    # Balanced: Dr Inventory 50 / Cr GRNI 50.
    total_d = sum(line.debit for line in je.lines.all())
    total_c = sum(line.credit for line in je.lines.all())
    assert total_d == total_c == 50


# ── Blocker 2 — manufacturing account mappings ───────────────────────────────
@pytest.mark.django_db
def test_manufacturing_accounts_exist_and_post():
    """WIP (1700) and FG (1400) — the accounts manufacturing posts to — exist after provisioning
    and a balanced WIP→FG entry posts cleanly through GLBus."""
    ws = uuid.uuid4()
    provision_accounting(ws)
    s = AccountingSettings.objects.get(workspace_id=ws)
    assert s.default_wip_account == "1700" and s.default_finished_goods_account == "1400"
    entry = GLBus.post(
        ws, date=datetime.date(2026, 6, 30), lines=[
            {"account_code": s.default_finished_goods_account, "debit": "100", "memo": "FG"},
            {"account_code": s.default_wip_account, "credit": "100", "memo": "WIP"}],
        source_module="manufacturing", actor_id=A)
    assert entry.status == "posted"


# ── Blocker 3 — silent GL failures removed ───────────────────────────────────
@pytest.mark.django_db
def test_emit_post_failure_records_audit_event():
    """The failure mechanism persists a visible ledger.post.failed audit event."""
    ws = uuid.uuid4()
    emit_post_failure(ws, module="inventory", source_ref="GRN-9",
                      error="unknown account '9999'", actor_id=A)
    ev = DomainEvent.objects.filter(workspace_id=ws, event_type="ledger.post.failed").first()
    assert ev is not None
    assert ev.payload["module"] == "inventory" and ev.payload["source_ref"] == "GRN-9"


@pytest.mark.django_db
def test_misconfigured_posting_raises_not_silent():
    """A configured-but-broken posting rule must RAISE (visible), never silently no-op."""
    from apps.inventory.models import Item, Warehouse
    from apps.inventory.services import InventoryService

    ws = uuid.uuid4()
    provision_accounting(ws)
    # Point the received rule at a non-existent account.
    rule = PostingRule.objects.get(workspace_id=ws, event_type="inventory.received")
    rule.template = [{"account_code": "9999", "side": "debit", "amount_field": "amount"},
                     {"account_code": "2050", "side": "credit", "amount_field": "amount"}]
    rule.save(update_fields=["template"])
    item = Item.objects.create(workspace_id=ws, sku="X", name="X", valuation_method="average")
    wh = Warehouse.objects.create(workspace_id=ws, code="MAIN", name="Main")
    with pytest.raises(LedgerError):
        InventoryService.receive(ws, item.id, wh.id, 1, "10", reference="GRN-X", actor_id=A)


# ── §9 per-flow accounting completeness: projects + procurement post real JEs ──
@pytest.mark.django_db
def test_project_cost_posts_journal():
    """Projects → Accounting: a WIP cost posts a balanced journal (Dr WIP / Cr accrual)."""
    from apps.projects.services import CostRollupService

    ws = uuid.uuid4()
    provision_accounting(ws)
    entry = CostRollupService.post_cost(
        workspace_id=ws, project_record_id=uuid.uuid4(), source="payroll", amount=750,
        entry_date=datetime.date(2026, 6, 30), reference="RUN-9", post_gl=True, actor_id=A)
    assert entry.journal_entry_id is not None
    je = JournalEntry.objects.get(workspace_id=ws, id=entry.journal_entry_id)
    assert je.source_module == "projects" and je.status == "posted"
    assert sum(line.debit for line in je.lines.all()) == \
        sum(line.credit for line in je.lines.all()) == 750


@pytest.mark.django_db
def test_procurement_vendor_bill_posts_journal():
    """Procurement → Accounting: posting a vendor bill creates a JE via the seeded
    vendor_bill.posted rule (provisioned automatically on solution install)."""
    from apps.procurement.blueprint import seed_procurement_template
    from apps.procurement.services import ProcurementService
    from apps.solution_templates import services as st

    ws = uuid.uuid4()
    st.install(template_id=seed_procurement_template().id, workspace_id=ws, installed_by=None)
    vb = ProcurementService.create_document(
        workspace_id=ws, entity_slug="vendor_bill",
        data={"amount": "150.00", "status": "approved"}, actor_id=None)
    ProcurementService.post_vendor_bill(workspace_id=ws, record_id=vb["id"])
    je = JournalEntry.objects.filter(workspace_id=ws, source_module="procurement")
    assert je.count() == 1
    assert sum(line.debit for line in je.first().lines.all()) == \
        sum(line.credit for line in je.first().lines.all()) == 150


# ── Blocker 4 — asset disposal idempotency ───────────────────────────────────
@pytest.mark.django_db
def test_asset_disposal_is_idempotent():
    from apps.assets.blueprint import seed_assets_template
    from apps.assets.models import DisposalRecord
    from apps.assets.services import AssetService, DisposalService
    from apps.solution_templates import services as st

    ws = uuid.uuid4()
    st.install(template_id=seed_assets_template().id, workspace_id=ws, installed_by=None)
    asset = AssetService.create_asset(
        workspace_id=ws, data={"name": "Van", "net_book_value": "1100"}, actor_id=A)

    r1 = DisposalService.dispose(workspace_id=ws, asset_record_id=asset["id"], method="sale",
                                 proceeds=500, book_value=1100, actor_id=A)
    r2 = DisposalService.dispose(workspace_id=ws, asset_record_id=asset["id"], method="sale",
                                 proceeds=500, book_value=1100, actor_id=A)
    assert r1.id == r2.id  # retry returned the same record
    assert DisposalRecord.objects.filter(workspace_id=ws, asset_record_id=asset["id"]).count() == 1
    # Exactly one disposal journal entry (proceeds > 0).
    assert JournalEntry.objects.filter(
        workspace_id=ws, source_module="assets", source_ref=str(asset["id"])).count() == 1


# ── Blocker 5 — project cost idempotency ─────────────────────────────────────
@pytest.mark.django_db
def test_project_cost_posting_is_idempotent():
    from apps.projects.models import ProjectCostEntry
    from apps.projects.services import CostRollupService

    ws = uuid.uuid4()
    project = uuid.uuid4()
    e1 = CostRollupService.post_cost(
        workspace_id=ws, project_record_id=project, source="payroll",
        amount=1000, reference="RUN-1", actor_id=A)
    e2 = CostRollupService.post_cost(
        workspace_id=ws, project_record_id=project, source="payroll",
        amount=1000, reference="RUN-1", actor_id=A)
    assert e1.id == e2.id
    entries = ProjectCostEntry.objects.filter(workspace_id=ws, project_record_id=project)
    assert entries.count() == 1
    assert sum(e.amount for e in entries) == 1000  # actual_cost not inflated by the retry
