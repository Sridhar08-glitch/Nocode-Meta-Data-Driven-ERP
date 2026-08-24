"""
Financial Dimension Framework (F9) certification.

Proves the GENERIC framework (one FinancialDimension + FinancialDimensionValue represents cost-center/
profit-center/region/fund/… + any custom dimension), GL integration via the additive JournalLine.
dimensions JSON map, deterministic validation (unknown/inactive/out-of-effective-date/required),
hierarchy roll-up, dimension-filtered + segment statements, and — critically — full backward
compatibility (postings with no dimensions are unchanged).
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.dimensions.services import DimensionError, DimensionService
from apps.financial_reports.services import StatementService
from apps.ledger.models import JournalLine
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus, LedgerError


def _d(v):
    return Decimal(str(v))


def _seed_cost_centers(ws):
    provision_accounting(ws)
    DimensionService.ensure_dimension(workspace_id=ws, code="cost_center", name="Cost Center",
                                      dimension_type="cost_center", is_hierarchical=True)
    DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code="ALL",
                               name="All")
    DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code="MKT",
                               name="Marketing", parent_code="ALL")
    DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code="SALES",
                               name="Sales", parent_code="ALL")


def _sale(ws, amount, *, cost_center=None, date=dt.date(2026, 1, 10)):
    dims = {"cost_center": cost_center} if cost_center else {}
    return GLBus.post(ws, date=date, lines=[
        {"account_code": "1100", "debit": str(amount)},
        {"account_code": "4000", "credit": str(amount), "dimensions": dims}],
        source_module="test", source_ref=f"s-{amount}-{cost_center}")


# ── the generic framework represents every dimension ────────────────────────────
@pytest.mark.django_db
def test_one_framework_represents_any_dimension():
    ws = uuid.uuid4()
    provision_accounting(ws)
    for code, dtype in [("cost_center", "cost_center"), ("profit_center", "profit_center"),
                        ("region", "geography"), ("fund", "fund"), ("sales_channel", "other")]:
        DimensionService.ensure_dimension(workspace_id=ws, code=code, dimension_type=dtype)
    from apps.dimensions.models import FinancialDimension
    # 5 different "dimension types" — ZERO per-dimension tables (all rows in one entity)
    assert FinancialDimension.objects.filter(workspace_id=ws).count() == 5


# ── GL integration + backward compatibility ─────────────────────────────────────
@pytest.mark.django_db
def test_legacy_posting_without_dimensions_unchanged():
    ws = uuid.uuid4()
    provision_accounting(ws)
    entry = _sale(ws, 100)                              # no dimensions
    line = entry.lines.get(account__code="4000")
    assert line.dimensions == {}                        # default, unchanged behaviour


@pytest.mark.django_db
def test_dimensions_stored_on_journal_line():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    entry = _sale(ws, 100, cost_center="MKT")
    line = entry.lines.get(account__code="4000")
    assert line.dimensions == {"cost_center": "MKT"}


@pytest.mark.django_db
def test_posting_rejects_unknown_dimension_value():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    with pytest.raises(LedgerError):
        _sale(ws, 100, cost_center="NOPE")             # not a defined value


@pytest.mark.django_db
def test_posting_rejects_inactive_value():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    from apps.dimensions.models import FinancialDimensionValue
    FinancialDimensionValue.objects.filter(workspace_id=ws, code="MKT").update(is_active=False)
    with pytest.raises(LedgerError):
        _sale(ws, 100, cost_center="MKT")


# ── validation ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_validate_map_and_required_enforcement():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    DimensionService.ensure_dimension(workspace_id=ws, code="region", is_required=True)
    DimensionService.add_value(workspace_id=ws, dimension_code="region", code="EMEA")
    assert DimensionService.validate_map(ws, {"cost_center": "MKT", "region": "EMEA"}) == []
    # required 'region' missing → error only when enforce_required
    assert DimensionService.validate_map(ws, {"cost_center": "MKT"}) == []
    errs = DimensionService.validate_map(ws, {"cost_center": "MKT"}, enforce_required=True)
    assert any("region" in e for e in errs)


@pytest.mark.django_db
def test_effective_dated_value():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code="NEW",
                               effective_from=dt.date(2026, 6, 1))
    assert DimensionService.validate_map(ws, {"cost_center": "NEW"},
                                         on_date=dt.date(2026, 3, 1))     # before effective
    assert DimensionService.validate_map(ws, {"cost_center": "NEW"},
                                         on_date=dt.date(2026, 7, 1)) == []


@pytest.mark.django_db
def test_hierarchy_descendants():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    kids = DimensionService.descendants(ws, "cost_center", "ALL")
    assert set(kids) == {"ALL", "MKT", "SALES"}


# ── dimension-aware statements ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_profit_and_loss_filtered_by_dimension():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    _sale(ws, 100, cost_center="MKT")
    _sale(ws, 60, cost_center="SALES")
    _sale(ws, 40)                                       # unassigned
    assert StatementService.profit_and_loss(ws)["total_revenue"] == "200.00"
    mkt = StatementService.profit_and_loss(ws, dimensions={"cost_center": "MKT"})
    assert mkt["total_revenue"] == "100.00"


@pytest.mark.django_db
def test_dimension_pnl_segment_report():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    _sale(ws, 100, cost_center="MKT")
    _sale(ws, 60, cost_center="SALES")
    seg = StatementService.dimension_pnl(ws, dimension_code="cost_center")
    rows = {r["value"]: r for r in seg["segments"]}
    assert rows["MKT"]["total_revenue"] == "100.00"
    assert rows["SALES"]["total_revenue"] == "60.00"


# ── governance ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_dimensions_workspace_isolated_and_capability():
    from apps.packaging.capabilities import capability_available
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    DimensionService.ensure_dimension(workspace_id=ws_a, code="cost_center")
    from apps.dimensions.models import FinancialDimension
    assert FinancialDimension.objects.filter(workspace_id=ws_a, code="cost_center").exists()
    assert not FinancialDimension.objects.filter(workspace_id=ws_b, code="cost_center").exists()
    assert capability_available("financial_dimensions")


def test_dimensions_is_crud_only_no_workflows():
    """Dimension maintenance is CRUD — no workflow executors added (correct per the review)."""
    from apps.workflows.executors import REGISTRY
    assert not any("dimension" in k for k in REGISTRY)


@pytest.mark.django_db
def test_add_value_unknown_dimension_errors():
    ws = uuid.uuid4()
    provision_accounting(ws)
    with pytest.raises(DimensionError):
        DimensionService.add_value(workspace_id=ws, dimension_code="ghost", code="X")


# keep JournalLine import meaningful
@pytest.mark.django_db
def test_reversal_carries_dimensions():
    ws = uuid.uuid4()
    _seed_cost_centers(ws)
    entry = _sale(ws, 100, cost_center="MKT")
    rev = GLBus.reverse(ws, entry.id)
    rev_line = rev.lines.get(account__code="4000")
    assert rev_line.dimensions == {"cost_center": "MKT"}
    assert JournalLine.objects.filter(workspace_id=ws, dimensions={"cost_center": "MKT"}).count() >= 1
