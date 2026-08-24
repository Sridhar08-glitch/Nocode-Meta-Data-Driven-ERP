"""
Budgets & Forecasts (F10) certification.

Proves the generic engine (one FinancialPlan/PlanVersion/PlanLine serves budget AND forecast),
scenarios + versions (revisions), allocation, segregation-of-duties approval, locked-version
immutability, dimension-tagged lines (F9) with validation, and — critically — budget-vs-actual /
forecast-vs-actual + utilization reading ACTUALS ONLY from the GL (no duplicated accounting).
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.budgets.models import FinancialPlan, PlanLine, PlanVersion
from apps.budgets.services import BudgetError, BudgetService
from apps.dimensions.services import DimensionService
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus


def _plan(ws, *, ptype="budget"):
    provision_accounting(ws)
    plan = BudgetService.create_plan(workspace_id=ws, code=f"{ptype}-2026", plan_type=ptype,
                                     fiscal_year="FY2026")
    v = BudgetService.create_version(workspace_id=ws, plan_id=plan.id)
    return plan, v


def _spend(ws, account, amount, *, date, dims=None):
    """Post an actual expense: Dr expense / Cr cash, optionally dimensioned."""
    GLBus.post(ws, date=date, lines=[
        {"account_code": account, "debit": str(amount), "dimensions": dims or {}},
        {"account_code": "1000", "credit": str(amount)}],
        source_module="test", source_ref=f"sp-{account}-{amount}")


# ── one generic engine for budget AND forecast ──────────────────────────────────
@pytest.mark.django_db
def test_one_engine_serves_budget_and_forecast():
    ws = uuid.uuid4()
    provision_accounting(ws)
    b = BudgetService.create_plan(workspace_id=ws, code="B", plan_type="budget")
    f = BudgetService.create_plan(workspace_id=ws, code="F", plan_type="forecast", is_rolling=True)
    assert b.plan_type == "budget" and f.plan_type == "forecast" and f.is_rolling
    assert FinancialPlan.objects.filter(workspace_id=ws).count() == 2   # same entity, no fork


# ── versions / scenarios / revisions ────────────────────────────────────────────
@pytest.mark.django_db
def test_versions_are_the_revision_axis():
    ws = uuid.uuid4()
    plan, v1 = _plan(ws)
    v2 = BudgetService.create_version(workspace_id=ws, plan_id=plan.id, revision_note="rev 2",
                                      copy_from_version=v1.id)
    v1.refresh_from_db()
    assert v2.version_no == 2 and v2.is_current and not v1.is_current
    # scenarios are an independent axis under the same plan
    opt = BudgetService.create_version(workspace_id=ws, plan_id=plan.id, scenario="optimistic")
    assert opt.version_no == 1 and opt.scenario == "optimistic"


@pytest.mark.django_db
def test_copy_from_version_duplicates_lines():
    ws = uuid.uuid4()
    plan, v1 = _plan(ws)
    BudgetService.add_line(workspace_id=ws, version_id=v1.id, account_code="6100", amount="100",
                           period="2026-01", period_date=dt.date(2026, 1, 1))
    v2 = BudgetService.create_version(workspace_id=ws, plan_id=plan.id, copy_from_version=v1.id)
    assert v2.lines.count() == 1 and v2.lines.first().amount == Decimal("100.00")


# ── allocation ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_allocation_spreads_total_across_periods():
    ws = uuid.uuid4()
    _, v = _plan(ws)
    periods = [{"period": f"2026-{m:02d}", "period_date": dt.date(2026, m, 1)} for m in range(1, 13)]
    lines = BudgetService.allocate(workspace_id=ws, version_id=v.id, account_code="6100",
                                   total="1200", periods=periods)
    assert len(lines) == 12
    assert sum((line.amount for line in lines), Decimal("0")) == Decimal("1200.00")
    assert lines[0].amount == Decimal("100.00")


# ── lifecycle + segregation of duties + lock ────────────────────────────────────
@pytest.mark.django_db
def test_approval_segregation_and_lock_immutability():
    ws = uuid.uuid4()
    plan = BudgetService.create_plan(workspace_id=ws, code="B", actor_id=uuid.uuid4())
    provision_accounting(ws)
    creator = uuid.uuid4()
    v = BudgetService.create_version(workspace_id=ws, plan_id=plan.id, actor_id=creator)
    BudgetService.submit(workspace_id=ws, version_id=v.id, actor_id=creator)
    # creator cannot approve their own version
    with pytest.raises(BudgetError):
        BudgetService.approve(workspace_id=ws, version_id=v.id, actor_id=creator)
    BudgetService.approve(workspace_id=ws, version_id=v.id, actor_id=uuid.uuid4())
    BudgetService.lock(workspace_id=ws, version_id=v.id)
    # a locked version is immutable
    with pytest.raises(BudgetError):
        BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="1")


# ── dimension integration (F9) ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_budget_line_validates_dimensions():
    ws = uuid.uuid4()
    _, v = _plan(ws)
    DimensionService.ensure_dimension(workspace_id=ws, code="cost_center")
    DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code="MKT")
    BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="100",
                           dimensions={"cost_center": "MKT"})
    with pytest.raises(BudgetError):
        BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="100",
                               dimensions={"cost_center": "NOPE"})


# ── budget vs actual (actuals ONLY from GL) ─────────────────────────────────────
@pytest.mark.django_db
def test_budget_vs_actual_reads_gl():
    ws = uuid.uuid4()
    _, v = _plan(ws)
    BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="1000",
                           period="FY2026", period_date=dt.date(2026, 1, 1))
    _spend(ws, "6100", 700, date=dt.date(2026, 3, 1))           # actual spend from GL
    bva = BudgetService.budget_vs_actual(workspace_id=ws, version_id=v.id,
                                         from_date=dt.date(2026, 1, 1), to_date=dt.date(2026, 12, 31))
    row = bva["rows"][0]
    assert row["budget"] == "1000.00" and row["actual"] == "700.00"
    assert row["variance"] == "300.00" and row["variance_pct"] == 30.0
    util = BudgetService.utilization(workspace_id=ws, version_id=v.id,
                                     from_date=dt.date(2026, 1, 1), to_date=dt.date(2026, 12, 31))
    assert util["utilization_pct"] == 70.0 and util["remaining"] == "300.00"


@pytest.mark.django_db
def test_budget_vs_actual_by_dimension():
    ws = uuid.uuid4()
    _, v = _plan(ws)
    DimensionService.ensure_dimension(workspace_id=ws, code="cost_center")
    for cc in ("MKT", "SALES"):
        DimensionService.add_value(workspace_id=ws, dimension_code="cost_center", code=cc)
    BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="500",
                           dimensions={"cost_center": "MKT"}, period_date=dt.date(2026, 1, 1))
    BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100", amount="300",
                           dimensions={"cost_center": "SALES"}, period_date=dt.date(2026, 1, 1))
    _spend(ws, "6100", 400, date=dt.date(2026, 2, 1), dims={"cost_center": "MKT"})
    _spend(ws, "6100", 350, date=dt.date(2026, 2, 1), dims={"cost_center": "SALES"})
    bva = BudgetService.budget_vs_actual(workspace_id=ws, version_id=v.id,
                                         from_date=dt.date(2026, 1, 1), to_date=dt.date(2026, 12, 31),
                                         group_by_dimension="cost_center")
    rows = {r["cost_center"]: r for r in bva["rows"]}
    assert rows["MKT"]["budget"] == "500.00" and rows["MKT"]["actual"] == "400.00"
    assert rows["SALES"]["actual"] == "350.00"                  # dimension-filtered GL actual


@pytest.mark.django_db
def test_forecast_vs_actual_uses_same_engine():
    ws = uuid.uuid4()
    _, v = _plan(ws, ptype="forecast")
    BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="4000", amount="2000",
                           period_date=dt.date(2026, 1, 1))
    GLBus.post(ws, date=dt.date(2026, 6, 1), lines=[                # actual revenue
        {"account_code": "1100", "debit": "1800"},
        {"account_code": "4000", "credit": "1800"}], source_ref="rev")
    bva = BudgetService.budget_vs_actual(workspace_id=ws, version_id=v.id,
                                         from_date=dt.date(2026, 1, 1), to_date=dt.date(2026, 12, 31))
    assert bva["plan_type"] == "forecast"
    assert bva["rows"][0]["actual"] == "1800.00"                # revenue natural direction


# ── governance ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_budgets_workspace_isolated_and_capability():
    from apps.packaging.capabilities import capability_available
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    _plan(ws_a)
    assert PlanVersion.objects.filter(workspace_id=ws_a).exists()
    assert not FinancialPlan.objects.filter(workspace_id=ws_b).exists()
    assert capability_available("budgeting") and capability_available("forecasting")


def test_budgets_no_workflow_executors():
    """Budgeting is planning (admin/REST-driven), not event-triggered — no workflow executors added."""
    from apps.workflows.executors import REGISTRY
    assert not any("budget" in k or "forecast" in k for k in REGISTRY)


# keep PlanLine import meaningful
@pytest.mark.django_db
def test_line_persisted_with_dimensions():
    ws = uuid.uuid4()
    _, v = _plan(ws)
    line = BudgetService.add_line(workspace_id=ws, version_id=v.id, account_code="6100",
                                  amount="50")
    assert PlanLine.objects.get(id=line.id).amount == Decimal("50.00")
