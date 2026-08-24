"""
Consolidation & Intercompany (F11) certification.

Proves: per-company GL books via ``JournalEntry.company_id``; intercompany transactions post through
GLBus (no new engine); consolidation runs are immutable versioned snapshots that NEVER touch
operational books; currency translation reuses F7 (closing/average + CTA); intercompany elimination;
persisted MinorityInterest + TranslationAdjustment; and BACKWARD COMPATIBILITY (single-company /
company_id=NULL postings + account_balance are byte-identical).
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.companies.services import CompanyService
from apps.consolidation.models import (
    ConsolidationRun,
    ConsolidationWorksheetLine,
    MinorityInterest,
    TranslationAdjustment,
)
from apps.consolidation.services import (
    ConsolidationError,
    ConsolidationService,
    IntercompanyService,
)
from apps.ledger.models import JournalEntry, LedgerAccount
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus


def _d(v):
    return Decimal(str(v))


def _bal(ws, code, *, company_id=None):
    acct = LedgerAccount.objects.get(workspace_id=ws, code=code)
    return GLBus.account_balance(ws, acct.id, company_id=company_id)


def _group(ws):
    provision_accounting(ws)
    grp = CompanyService.ensure_company(workspace_id=ws, code="GRP", functional_currency="USD",
                                        is_group=True)
    a = CompanyService.ensure_company(workspace_id=ws, code="A", functional_currency="USD",
                                      parent_code="GRP")
    b = CompanyService.ensure_company(workspace_id=ws, code="B", functional_currency="USD",
                                      parent_code="GRP")
    return grp, a, b


def _sale(ws, company_id, amount, *, date=dt.date(2026, 1, 10)):
    return GLBus.post(ws, date=date, company_id=company_id, lines=[
        {"account_code": "1100", "debit": str(amount)},
        {"account_code": "4000", "credit": str(amount)}], source_ref=f"s-{company_id}-{amount}")


# ── backward compatibility (single company / NULL) ──────────────────────────────
@pytest.mark.django_db
def test_legacy_posting_without_company_unchanged():
    ws = uuid.uuid4()
    provision_accounting(ws)
    entry = GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1100", "debit": "100"},
        {"account_code": "4000", "credit": "100"}], source_ref="legacy")
    assert entry.company_id is None and entry.ledger_id is None
    # workspace-wide balance unchanged (no company filter)
    assert _bal(ws, "1100") == _d("100.00")


# ── per-company books ───────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_company_scoped_balances():
    ws = uuid.uuid4()
    _grp, a, b = _group(ws)
    _sale(ws, a.id, 100)
    _sale(ws, b.id, 60)
    assert _bal(ws, "4000") == _d("-160.00")               # workspace-wide (both companies)
    assert _bal(ws, "4000", company_id=a.id) == _d("-100.00")   # company A only
    assert _bal(ws, "4000", company_id=b.id) == _d("-60.00")


@pytest.mark.django_db
def test_statements_filter_by_company():
    from apps.financial_reports.services import StatementService
    ws = uuid.uuid4()
    _grp, a, b = _group(ws)
    _sale(ws, a.id, 100)
    _sale(ws, b.id, 60)
    assert StatementService.profit_and_loss(ws)["total_revenue"] == "160.00"
    assert StatementService.profit_and_loss(ws, company_id=a.id)["total_revenue"] == "100.00"


# ── intercompany via GLBus (no new engine) ──────────────────────────────────────
@pytest.mark.django_db
def test_intercompany_posts_paired_entries():
    ws = uuid.uuid4()
    _grp, a, b = _group(ws)
    out = IntercompanyService.post_transaction(
        workspace_id=ws, from_company=a.id, to_company=b.id, amount="500",
        description="services", external_ref="ic1")
    assert out["posted"] is True
    # A owes B: A has IC-Payable, B has IC-Receivable
    assert _bal(ws, "2900", company_id=a.id) == _d("-500.00")   # IC payable (liability) in A
    assert _bal(ws, "1900", company_id=b.id) == _d("500.00")    # IC receivable (asset) in B
    # idempotent
    assert IntercompanyService.post_transaction(
        workspace_id=ws, from_company=a.id, to_company=b.id, amount="500",
        external_ref="ic1")["posted"] is False


# ── consolidation run (immutable snapshot, elimination) ─────────────────────────
@pytest.mark.django_db
def test_consolidation_run_eliminates_intercompany_and_balances():
    ws = uuid.uuid4()
    grp, a, b = _group(ws)
    _sale(ws, a.id, 1000)
    _sale(ws, b.id, 500)
    IntercompanyService.post_transaction(workspace_id=ws, from_company=a.id, to_company=b.id,
                                         amount="300", external_ref="ic1")
    run = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    assert run.balanced is True and run.company_count == 2
    # the consolidated worksheet DETAIL is queryable first-class rows (company_code="" = group total)
    consolidated = {ln.account_code: ln.translated_balance for ln in
                    ConsolidationWorksheetLine.objects.filter(workspace_id=ws, run=run,
                                                              company_code="")}
    assert consolidated.get("1900", _d(0)) == _d("0.00")   # intercompany eliminated to zero
    assert consolidated.get("2900", _d(0)) == _d("0.00")
    assert run.worksheet["eliminations"]                   # elimination recorded in the summary


@pytest.mark.django_db
def test_consolidation_reruns_create_versions_without_touching_books():
    ws = uuid.uuid4()
    grp, a, b = _group(ws)
    _sale(ws, a.id, 100)
    entries_before = JournalEntry.objects.filter(workspace_id=ws).count()
    r1 = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    r2 = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    assert r1.version_no == 1 and r2.version_no == 2
    # consolidation posted NO operational journals (books untouched)
    assert JournalEntry.objects.filter(workspace_id=ws).count() == entries_before
    assert ConsolidationRun.objects.filter(workspace_id=ws).count() == 2


# ── currency translation (reuse F7) + CTA ───────────────────────────────────────
@pytest.mark.django_db
def test_translation_reuses_f7_and_persists_adjustment():
    from apps.currency.services import CurrencyService
    ws = uuid.uuid4()
    provision_accounting(ws)
    CurrencyService.set_base(workspace_id=ws, code="USD")
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10",
                             rate_type="closing")
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.05",
                             rate_type="average")
    grp = CompanyService.ensure_company(workspace_id=ws, code="GRP", functional_currency="USD",
                                        is_group=True)
    eu = CompanyService.ensure_company(workspace_id=ws, code="EU", functional_currency="EUR",
                                       parent_code="GRP")
    # EUR company posts in EUR
    GLBus.post(ws, date=dt.date(2026, 1, 5), company_id=eu.id, lines=[
        {"account_code": "1100", "debit": "100", "currency": "EUR", "fx_rate": "1.10"},
        {"account_code": "4000", "credit": "100", "currency": "EUR", "fx_rate": "1.10"}],
        source_ref="eu")
    run = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    ta = TranslationAdjustment.objects.get(workspace_id=ws, run=run, company_code="EU")
    assert ta.closing_rate == _d("1.10000000") and ta.average_rate == _d("1.05000000")
    assert run.balanced is True                            # CTA plug keeps it balanced


# ── minority interest (persisted, first-class) ──────────────────────────────────
@pytest.mark.django_db
def test_minority_interest_persisted():
    ws = uuid.uuid4()
    grp, a, b = _group(ws)
    # A is 70% owned → 30% minority interest of A's net assets
    CompanyService.set_ownership(workspace_id=ws, parent_code="GRP", subsidiary_code="A",
                                 ownership_pct="70")
    # give A net assets: Dr Cash 1000 / Cr Equity 1000
    GLBus.post(ws, date=dt.date(2026, 1, 1), company_id=a.id, lines=[
        {"account_code": "1000", "debit": "1000"},
        {"account_code": "3000", "credit": "1000"}], source_ref="cap")
    run = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    mi = MinorityInterest.objects.get(workspace_id=ws, run=run, company_code="A")
    assert mi.ownership_pct == _d("70.0000") and mi.minority_amount == _d("300.00")   # 30% of 1000
    assert run.total_minority_interest == _d("300.00")


# ── governance ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_worksheet_is_queryable_first_class_rows():
    """The worksheet detail is queryable rows (per-company cells + consolidated), not a JSON blob —
    so a large consolidation can be queried/audited/diffed by company + account."""
    ws = uuid.uuid4()
    grp, a, b = _group(ws)
    _sale(ws, a.id, 100)
    _sale(ws, b.id, 60)
    run = ConsolidationService.run(workspace_id=ws, group_id=grp.id, presentation_currency="USD")
    # per-company cells exist and are queryable
    a_rev = ConsolidationWorksheetLine.objects.get(workspace_id=ws, run=run, company_code="A",
                                                   account_code="4000")
    assert a_rev.translated_balance == _d("-100.00")
    assert ConsolidationWorksheetLine.objects.filter(workspace_id=ws, run=run,
                                                     company_code="B").exists()
    # consolidated group total for revenue = -160
    cons = ConsolidationWorksheetLine.objects.get(workspace_id=ws, run=run, company_code="",
                                                  account_code="4000")
    assert cons.translated_balance == _d("-160.00")
    # the JSON summary no longer carries the per-account detail (moved to rows)
    assert "consolidated" not in run.worksheet and run.worksheet["line_count"] > 0


@pytest.mark.django_db
def test_consolidation_capabilities_registered():
    from apps.packaging.capabilities import capability_available
    assert capability_available("consolidation") and capability_available("intercompany")


@pytest.mark.django_db
def test_empty_group_errors():
    ws = uuid.uuid4()
    provision_accounting(ws)
    grp = CompanyService.ensure_company(workspace_id=ws, code="GRP", is_group=True)
    with pytest.raises(ConsolidationError):
        ConsolidationService.run(workspace_id=ws, group_id=grp.id)
