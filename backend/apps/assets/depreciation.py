"""
Depreciation calculator (Phase P2.9) — pure functions, batch-safe.

Supports straight-line, declining-balance and double-declining-balance. Per-period (monthly)
amounts; never depreciates net book value below salvage. Used by ``DepreciationService`` to
produce immutable ``DepreciationEntry`` rows.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except Exception:  # noqa: BLE001
        return Decimal("0.00")


def period_amount(*, method, cost, salvage, useful_life_months, accumulated,
                  period_index) -> Decimal:
    """Depreciation for the NEXT period given the accumulated-to-date. Returns 0 once the asset
    is fully depreciated (net book value == salvage) or the life is exhausted."""
    cost = money(cost)
    salvage = money(salvage)
    accumulated = money(accumulated)
    life = max(int(useful_life_months or 0), 0)
    nbv = money(cost - accumulated)
    depreciable_remaining = money(nbv - salvage)
    if life == 0 or depreciable_remaining <= 0:
        return Decimal("0.00")
    if period_index >= life:
        # Beyond planned life — book any remaining depreciable amount once.
        return depreciable_remaining if method == "straight_line" else Decimal("0.00")

    if method == "straight_line":
        amount = money((cost - salvage) / Decimal(life))
    elif method == "declining_balance":
        annual_rate = Decimal(1) / (Decimal(life) / Decimal(12))
        amount = money(nbv * annual_rate / Decimal(12))
    elif method == "double_declining":
        annual_rate = Decimal(2) / (Decimal(life) / Decimal(12))
        amount = money(nbv * annual_rate / Decimal(12))
    else:
        amount = money((cost - salvage) / Decimal(life))

    # Never depreciate below salvage.
    return amount if amount <= depreciable_remaining else depreciable_remaining


def full_schedule(*, method, cost, salvage, useful_life_months, start_date=None) -> list[dict]:
    """Preview the complete schedule (for display). Stops when fully depreciated."""
    rows: list[dict] = []
    accumulated = Decimal("0.00")
    for i in range(int(useful_life_months or 0) + 1):
        amt = period_amount(method=method, cost=cost, salvage=salvage,
                            useful_life_months=useful_life_months, accumulated=accumulated,
                            period_index=i)
        if amt <= 0:
            break
        accumulated = money(accumulated + amt)
        rows.append({"period_index": i, "amount": amt, "accumulated": accumulated,
                     "net_book_value": money(money(cost) - accumulated)})
    return rows
