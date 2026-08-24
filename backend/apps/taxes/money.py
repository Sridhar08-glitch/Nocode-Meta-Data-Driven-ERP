"""Decimal money/rate helpers — quantize to 2 places (money) matching ledger precision."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")
_RATE = Decimal("0.000001")


def money(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def rate(value) -> Decimal:
    """A tax rate as a PERCENT (e.g. 15 → 15%). Kept at 6 dp for compounding precision."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value)).quantize(_RATE, rounding=ROUND_HALF_UP)
