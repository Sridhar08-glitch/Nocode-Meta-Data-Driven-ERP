"""
Payroll calculator (Phase P2.8) — the gross→net engine.

Pure functions (no DB) so they are trivially testable and batch-safe (no per-employee N+1).
Earnings are computed first (in sequence) to establish ``gross``; deductions and benefits are
then computed with ``gross`` in scope. Component formulas evaluate through the safe evaluator.
Proration scales earnings for mid-period join/leave. Extra lines (overtime, loans, advances,
adjustments, statutory/country components) merge in as additional payslip lines.
"""
from __future__ import annotations

from decimal import Decimal

from .countries import get_adapter
from .formula import evaluate, money


def _component_amount(comp: dict, context: dict) -> Decimal:
    calc = comp.get("calc_type", "fixed")
    if calc == "formula":
        return evaluate(comp.get("formula", ""), context)
    if calc == "percent":
        base = Decimal(str(context.get(comp.get("base_code", ""), 0)))
        return money(base * money(comp.get("amount", 0)) / Decimal("100"))
    return money(comp.get("amount", 0))


def calculate(
    *,
    components: list[dict],
    base_salary,
    proration: Decimal = Decimal("1"),
    extra_lines: list[dict] | None = None,
    country: str | None = None,
    context_extra: dict | None = None,
) -> dict:
    """Compute a payslip. ``components`` are sorted by sequence within type.

    Returns ``{lines, total_earnings, gross_pay, total_deductions, net_pay, total_benefits}``.
    """
    proration = Decimal(str(proration if proration is not None else 1))
    base = money(base_salary)
    context: dict = {"basic": float(base), "base_salary": float(base)}
    context.update({k: float(money(v)) for k, v in (context_extra or {}).items()})

    earnings = sorted([c for c in components if c.get("component_type") == "earning"],
                      key=lambda c: c.get("sequence", 100))
    others = sorted([c for c in components if c.get("component_type") != "earning"],
                    key=lambda c: c.get("sequence", 100))

    lines: list[dict] = []
    total_earnings = Decimal("0.00")

    # Pass 1 — earnings (establish gross). Compute each at FULL value (so percent/formula
    # components reference un-prorated bases), then prorate the line amount + total.
    for c in earnings:
        full = _component_amount(c, context)
        context[c["code"]] = float(full)
        amt = money(full * proration)
        total_earnings += amt
        lines.append(_line(c, amt))

    # Extra EARNING lines (overtime, earning adjustments, statutory contributions paid to employee).
    for ex in (extra_lines or []):
        if ex.get("component_type") == "earning":
            amt = money(ex.get("amount", 0))
            context[ex.get("code", "extra")] = float(amt)
            total_earnings += amt
            lines.append(_line(ex, amt, source=ex.get("source", "adjustment")))

    gross = money(total_earnings)
    context["gross"] = float(gross)

    # Country statutory components (tax/pension/social security) computed on gross/basic.
    for sc in get_adapter(country).statutory_components(
            gross=gross, basic=base, context=dict(context)):
        others = others + [dict(sc, calc_type="fixed", sequence=sc.get("sequence", 500))]

    total_deductions = Decimal("0.00")
    total_benefits = Decimal("0.00")

    # Pass 2 — deductions + benefits (gross in scope).
    for c in others:
        amt = _component_amount(c, context)
        context[c["code"]] = float(amt)
        if c.get("component_type") == "deduction":
            total_deductions += amt
            lines.append(_line(c, amt))
        else:  # benefit — tracked independently, not in net
            total_benefits += amt
            lines.append(_line(c, amt))

    # Extra DEDUCTION lines (loan/advance recovery, absence/penalty, deduction adjustments).
    for ex in (extra_lines or []):
        if ex.get("component_type") == "deduction":
            amt = money(ex.get("amount", 0))
            total_deductions += amt
            lines.append(_line(ex, amt, source=ex.get("source", "adjustment")))

    net = money(gross - total_deductions)
    for i, ln in enumerate(lines):
        ln["sequence"] = ln.get("sequence", 100) + i  # stable display order
    return {
        "lines": lines,
        "total_earnings": gross,
        "gross_pay": gross,
        "total_deductions": money(total_deductions),
        "total_benefits": money(total_benefits),
        "net_pay": net,
    }


def _line(comp: dict, amount: Decimal, source: str = "computed") -> dict:
    return {
        "code": comp.get("code", ""),
        "name": comp.get("name", comp.get("code", "")),
        "component_type": comp.get("component_type", "earning"),
        "amount": amount,
        "formula_version": comp.get("formula_version", 0),
        "source": source,
        "sequence": comp.get("sequence", 100),
    }


def proration_factor(*, period_start, period_end, worked_start=None, worked_end=None) -> Decimal:
    """Fraction of the period an employee is active (mid-period join/leave). 1 = full period."""
    total_days = (period_end - period_start).days + 1
    if total_days <= 0:
        return Decimal("1")
    start = max(worked_start, period_start) if worked_start else period_start
    end = min(worked_end, period_end) if worked_end else period_end
    worked = (end - start).days + 1
    worked = max(0, min(worked, total_days))
    return (Decimal(worked) / Decimal(total_days)).quantize(Decimal("0.000001"))
