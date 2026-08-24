"""
Budget / Cost-Rollup / Profitability / Earned-Value engine (Phase P2.10) — pure, batch-safe.

Money-exact (Decimal, 2dp). Powers Module 19 (budget), 20 (cost rollup), 22 (profitability),
23 (earned value). The service feeds these with project fields + cost entries + task progress.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def money(v) -> Decimal:
    try:
        return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except Exception:  # noqa: BLE001
        return Decimal("0.00")


def budget_status(*, planned_budget, actual_cost, forecast_cost=None) -> dict:
    planned = money(planned_budget)
    actual = money(actual_cost)
    forecast = money(forecast_cost) if forecast_cost is not None else actual
    return {
        "planned_budget": str(planned), "actual_cost": str(actual),
        "forecast_cost": str(forecast),
        "remaining_budget": str(money(planned - actual)),
        "budget_variance": str(money(planned - forecast)),
        "over_budget": actual > planned,
        "utilization_percent": float(money(actual / planned * 100)) if planned > 0 else 0.0,
    }


def cost_rollup(entries: list[dict]) -> dict:
    """entries: [{source, amount}]. Returns total + per-source breakdown."""
    by_source: dict = {}
    total = Decimal("0.00")
    for e in entries:
        amt = money(e.get("amount"))
        src = e.get("source", "other")
        by_source[src] = money(by_source.get(src, Decimal("0.00")) + amt)
        total += amt
    return {"total_cost": str(money(total)),
            "by_source": {k: str(v) for k, v in by_source.items()}}


def profitability(*, revenue, cost) -> dict:
    rev = money(revenue)
    c = money(cost)
    profit = money(rev - c)
    margin = float(money(profit / rev * 100)) if rev > 0 else 0.0
    return {"revenue": str(rev), "cost": str(c), "profit": str(profit),
            "margin_percent": margin,
            "burn_rate": str(c)}  # period burn = cost to date (service may divide by periods)


def earned_value(*, planned_value, earned_value, actual_cost, budget_at_completion=None) -> dict:
    """EVM: CV=EV−AC, SV=EV−PV, CPI=EV/AC, SPI=EV/PV, EAC=BAC/CPI."""
    pv = money(planned_value)
    ev = money(earned_value)
    ac = money(actual_cost)
    bac = money(budget_at_completion) if budget_at_completion is not None else pv
    cpi = float(money(ev / ac)) if ac > 0 else 0.0
    spi = float(money(ev / pv)) if pv > 0 else 0.0
    eac = money(bac / Decimal(str(cpi))) if cpi > 0 else bac
    return {
        "planned_value": str(pv), "earned_value": str(ev), "actual_cost": str(ac),
        "budget_at_completion": str(bac),
        "cost_variance": str(money(ev - ac)), "schedule_variance": str(money(ev - pv)),
        "cpi": cpi, "spi": spi, "estimate_at_completion": str(eac),
    }
