"""
Payroll formula evaluation (Phase P2.8).

REUSES the platform's safe AST evaluator (``apps.computed.services.safe_eval`` — no ``eval``,
rejects calls/imports/attribute access) — payroll never builds its own evaluator. Because the
evaluator works in native Python numerics (Decimal × float raises), we evaluate in ``float``
space and quantize the result back to money-exact ``Decimal`` (2dp, ROUND_HALF_UP). Formulas are
versioned + snapshotted on the payslip so historical pay never recalculates.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from apps.computed.services import ComputedError, safe_eval

CENTS = Decimal("0.01")


class PayrollFormulaError(Exception):  # noqa: N818 — domain error
    pass


def money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def evaluate(formula: str, context: dict) -> Decimal:
    """Evaluate a component formula against a numeric context → money-exact Decimal.

    ``context`` maps variable name → number (component codes, ``basic``, ``gross``, etc.).
    Unknown names resolve to 0 (per the safe evaluator). Raises ``PayrollFormulaError`` on
    unsafe/invalid expressions.
    """
    if not formula or not formula.strip():
        return Decimal("0.00")
    names = {k: float(money(v)) for k, v in (context or {}).items()}
    try:
        result = safe_eval(formula, names)
    except ComputedError as exc:
        raise PayrollFormulaError(f"Invalid payroll formula {formula!r}: {exc}") from exc
    return money(result)


def referenced_names(formula: str) -> set[str]:
    """Variable names a formula reads (for dependency validation)."""
    from apps.computed.services import _referenced_names
    try:
        return set(_referenced_names(formula or ""))
    except ComputedError:
        return set()
