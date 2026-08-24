"""Decimal money helper — quantize to 2 places (matches ledger MONEY precision)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def money(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)
