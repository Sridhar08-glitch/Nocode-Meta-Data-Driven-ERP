"""
Financial KPI evaluators (F13) — the NATIVE finance evaluators the frozen Analytics platform calls.

Each evaluator is `fn(workspace_id) -> Decimal`, registered into `apps.analytics.registry` under a
`finance_*` native_key (§2: no second KPI engine). Every figure is READ from an existing platform —
`StatementService` (GL statements), `CashService`, `SettlementService` (aging), `LiquidityService`
(treasury/F12), `BudgetService`, `CurrencyService`/GL accounts, `CompanyService`/consolidation — so
F13 owns ZERO accounting: it computes ratios over numbers other engines already produce. Deterministic
(no AI). `_base(ws)` collects the shared figures ONCE per (ws, as_of) via a short micro-cache so a
scorecard of ~30 KPIs collapses to a handful of underlying statement calls (Gate 8: query count is
O(KPIs), independent of journal-line volume — no N+1).
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

CENTS = Decimal("0.01")
_CACHE_TTL = 5  # seconds — collapse repeated statement calls within one scorecard/dashboard render


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _div(a, b) -> Decimal:
    a, b = _d(a), _d(b)
    return (a / b) if b != 0 else Decimal("0")


def _acct_bal(workspace_id, code, as_of=None) -> Decimal:
    """Net movement (debit − credit) on one account by code, via GLBus (0 if the account is absent)."""
    from apps.ledger.models import LedgerAccount
    from apps.ledger.services import GLBus
    acct = LedgerAccount.objects.filter(workspace_id=workspace_id, code=str(code)).first()
    if acct is None:
        return Decimal("0")
    return GLBus.account_balance(workspace_id, acct.id, as_of=as_of)


def invalidate(workspace_id) -> None:
    cache.delete(f"finkpi:base:{workspace_id}")


def _base(workspace_id) -> dict:
    """Shared base figures for all finance KPIs — computed ONCE per workspace (micro-cached), by
    REUSING the statement / cash / settlement / treasury / consolidation platforms."""
    key = f"finkpi:base:{workspace_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    from apps.financial_reports.services import StatementService
    from apps.settlement.services import SettlementService
    from apps.treasury.services import LiquidityService

    now = timezone.now().date()
    year_start = _dt.date(now.year, 1, 1)

    bs = StatementService.balance_sheet(workspace_id, as_of=now)
    pnl = StatementService.profit_and_loss(workspace_id, from_date=year_start, to_date=now)

    def _code_amt(rows):                      # {int(code): Decimal(amount)}
        out = {}
        for r in rows:
            try:
                out[int(r["code"])] = _d(r["amount"])
            except (ValueError, KeyError):
                continue
        return out

    a = _code_amt(bs["assets"])
    liab = _code_amt(bs["liabilities"])
    exp = {}
    for r in pnl["expenses"]:
        try:
            exp[int(r["code"])] = _d(r["amount"])
        except (ValueError, KeyError):
            continue

    current_assets = sum((v for c, v in a.items() if 1000 <= c < 1500), Decimal("0"))
    noncurrent_assets = sum((v for c, v in a.items() if c >= 1500), Decimal("0"))
    current_liabilities = sum((v for c, v in liab.items() if 2000 <= c < 2600), Decimal("0"))
    long_term_debt = sum((v for c, v in liab.items() if c >= 2600), Decimal("0"))
    inventory = a.get(1200, Decimal("0"))
    cash = a.get(1000, Decimal("0")) + a.get(1010, Decimal("0"))
    ar = a.get(1100, Decimal("0"))
    ap = liab.get(2000, Decimal("0"))

    revenue = _d(pnl["total_revenue"])
    expenses = _d(pnl["total_expenses"])
    net_income = _d(pnl["net_income"])
    cogs = exp.get(5000, Decimal("0"))
    interest_expense = exp.get(6500, Decimal("0"))
    depreciation = exp.get(6300, Decimal("0"))
    opex = expenses - cogs - interest_expense               # SG&A / operating (ex-COGS, ex-interest)
    operating_income = revenue - cogs - opex               # == net_income + interest_expense

    try:
        liq = LiquidityService.position(workspace_id)
    except Exception:  # noqa: BLE001
        liq = {"net_liquidity": "0", "borrowings": "0", "investments": "0"}

    try:
        ar_aging = SettlementService.aging(workspace_id, direction="debit", as_of=now)
        ar_total = _d(ar_aging["grand_total"])
        ar_overdue = ar_total - _d(ar_aging["totals"].get("current", 0))
    except Exception:  # noqa: BLE001
        ar_total, ar_overdue = ar, Decimal("0")

    months_elapsed = max(1, now.month)
    tax_liability = -_acct_bal(workspace_id, 2200) - _acct_bal(workspace_id, 2210)
    fx_net = (-_acct_bal(workspace_id, 4930)) - _acct_bal(workspace_id, 6960)  # gain − loss
    ic_net = _acct_bal(workspace_id, 1900) + _acct_bal(workspace_id, 2900)

    data = {
        "current_assets": current_assets, "noncurrent_assets": noncurrent_assets,
        "total_assets": _d(bs["total_assets"]), "inventory": inventory, "cash": cash, "ar": ar,
        "current_liabilities": current_liabilities, "long_term_debt": long_term_debt, "ap": ap,
        "total_liabilities": _d(bs["total_liabilities"]), "total_equity": _d(bs["total_equity"]),
        "revenue": revenue, "expenses": expenses, "net_income": net_income, "cogs": cogs,
        "opex": opex, "operating_income": operating_income, "interest_expense": interest_expense,
        "depreciation": depreciation, "months_elapsed": months_elapsed,
        "net_liquidity": _d(liq["net_liquidity"]), "borrowings": _d(liq["borrowings"]),
        "investments": _d(liq["investments"]), "ar_total": ar_total, "ar_overdue": ar_overdue,
        "tax_liability": tax_liability, "fx_net": fx_net, "ic_net": ic_net,
    }
    cache.set(key, data, _CACHE_TTL)
    return data


def _prior_year_revenue(workspace_id) -> Decimal:
    from apps.financial_reports.services import StatementService
    now = timezone.now().date()
    py = now.year - 1
    pnl = StatementService.profit_and_loss(
        workspace_id, from_date=_dt.date(py, 1, 1),
        to_date=_dt.date(py, now.month, min(now.day, 28)))
    return _d(pnl["total_revenue"])


def _budget_variance_pct(workspace_id) -> Decimal:
    """Best-effort total budget variance %% of the most recent locked/approved budget version."""
    from apps.budgets.models import FinancialPlan, PlanVersion
    from apps.budgets.services import BudgetService
    plan_ids = list(FinancialPlan.objects.filter(
        workspace_id=workspace_id, plan_type="budget").values_list("id", flat=True))
    if not plan_ids:
        return Decimal("0")
    ver = (PlanVersion.objects.filter(workspace_id=workspace_id, plan_id__in=plan_ids)
           .order_by("-created_at").first())
    if ver is None:
        return Decimal("0")
    bva = BudgetService.budget_vs_actual(workspace_id=workspace_id, version_id=ver.id)
    budget_total = _d(bva.get("total_budget") or bva.get("budget") or 0)
    actual_total = _d(bva.get("total_actual") or bva.get("actual") or 0)
    return _div(actual_total - budget_total, budget_total) * 100


def _company_count(workspace_id) -> Decimal:
    from apps.companies.models import Company
    return Decimal(Company.objects.filter(workspace_id=workspace_id).count())


# ── the evaluator functions (each returns a Decimal) ─────────────────────────────
def _pct(x) -> Decimal:
    return (_d(x)).quantize(Decimal("0.01"))


EVALUATORS = {
    # Liquidity
    "current_ratio": lambda ws: _div(_base(ws)["current_assets"], _base(ws)["current_liabilities"]),
    "quick_ratio": lambda ws: _div(_base(ws)["current_assets"] - _base(ws)["inventory"],
                                   _base(ws)["current_liabilities"]),
    "cash_ratio": lambda ws: _div(_base(ws)["cash"], _base(ws)["current_liabilities"]),
    # Working capital
    "working_capital": lambda ws: _base(ws)["current_assets"] - _base(ws)["current_liabilities"],
    "working_capital_ratio": lambda ws: _div(
        _base(ws)["current_assets"] - _base(ws)["current_liabilities"], _base(ws)["total_assets"]),
    # Cash
    "cash_balance": lambda ws: _base(ws)["cash"],
    "cash_runway_months": lambda ws: _div(
        _base(ws)["cash"], _div(_base(ws)["expenses"], _base(ws)["months_elapsed"])),
    # Profitability
    "gross_margin_pct": lambda ws: _pct(_div(_base(ws)["revenue"] - _base(ws)["cogs"],
                                             _base(ws)["revenue"]) * 100),
    "operating_margin_pct": lambda ws: _pct(_div(_base(ws)["operating_income"],
                                                 _base(ws)["revenue"]) * 100),
    "net_profit_margin_pct": lambda ws: _pct(_div(_base(ws)["net_income"],
                                                  _base(ws)["revenue"]) * 100),
    "ebitda": lambda ws: (_base(ws)["operating_income"] + _base(ws)["depreciation"]),
    # Revenue / Expense
    "gl_total_revenue": lambda ws: _base(ws)["revenue"],
    "gl_total_expense": lambda ws: _base(ws)["expenses"],
    "opex_ratio_pct": lambda ws: _pct(_div(_base(ws)["opex"], _base(ws)["revenue"]) * 100),
    "revenue_growth_pct": lambda ws: _pct(_div(
        _base(ws)["revenue"] - _prior_year_revenue(ws), _prior_year_revenue(ws)) * 100),
    # Efficiency
    "dso_days": lambda ws: _pct(_div(_base(ws)["ar"], _base(ws)["revenue"]) * 365),
    "dpo_days": lambda ws: _pct(_div(_base(ws)["ap"], _base(ws)["cogs"]) * 365),
    "dio_days": lambda ws: _pct(_div(_base(ws)["inventory"], _base(ws)["cogs"]) * 365),
    "cash_conversion_cycle": lambda ws: (
        _pct(_div(_base(ws)["ar"], _base(ws)["revenue"]) * 365)
        + _pct(_div(_base(ws)["inventory"], _base(ws)["cogs"]) * 365)
        - _pct(_div(_base(ws)["ap"], _base(ws)["cogs"]) * 365)),
    # AR / AP
    "ar_balance": lambda ws: _base(ws)["ar"],
    "ap_balance": lambda ws: _base(ws)["ap"],
    "ar_overdue_pct": lambda ws: _pct(_div(_base(ws)["ar_overdue"], _base(ws)["ar_total"]) * 100),
    # Treasury (F12)
    "net_liquidity": lambda ws: _base(ws)["net_liquidity"],
    "total_borrowings": lambda ws: _base(ws)["borrowings"],
    "total_investments": lambda ws: _base(ws)["investments"],
    # Leverage / Capital structure
    "debt_to_equity": lambda ws: _div(_base(ws)["total_liabilities"], _base(ws)["total_equity"]),
    "debt_ratio": lambda ws: _div(_base(ws)["total_liabilities"], _base(ws)["total_assets"]),
    "equity_ratio": lambda ws: _div(_base(ws)["total_equity"], _base(ws)["total_assets"]),
    "interest_coverage": lambda ws: _div(_base(ws)["operating_income"],
                                         _base(ws)["interest_expense"]),
    # Returns
    "return_on_assets_pct": lambda ws: _pct(_div(_base(ws)["net_income"],
                                                 _base(ws)["total_assets"]) * 100),
    "return_on_equity_pct": lambda ws: _pct(_div(_base(ws)["net_income"],
                                                 _base(ws)["total_equity"]) * 100),
    # Budget / Consolidation / FX / Tax
    "budget_variance_pct": lambda ws: _pct(_budget_variance_pct(ws)),
    "company_count": lambda ws: _company_count(ws),
    "intercompany_balance": lambda ws: _base(ws)["ic_net"],
    "fx_net_impact": lambda ws: _base(ws)["fx_net"],
    "tax_liability": lambda ws: _base(ws)["tax_liability"],
}


def register_all() -> int:
    """Register every finance evaluator into the frozen analytics registry as ``finance_<code>``."""
    from apps.analytics import registry
    for code, fn in EVALUATORS.items():
        registry.register(f"finance_{code}", fn)
    return len(EVALUATORS)
