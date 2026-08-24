"""
Multi-Currency services (Financial Platform).

``CurrencyService`` — the single reusable entry point for the currency master + FX conversion. Pure,
deterministic. GLBus calls ``base_rate`` to record each line's base-currency equivalent; the Settlement
engine calls ``convert`` to compute realized FX gain/loss. BACKWARD-COMPATIBLE: if a workspace has no
base currency configured, ``base_code`` is "" and ``base_rate`` returns 1 (transaction == base), so all
existing single-currency postings are unaffected.
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .models import Currency, ExchangeRate

RATE_Q = Decimal("0.00000001")


class CurrencyError(Exception):  # noqa: N818 — domain error
    pass


def _rate(v) -> Decimal:
    return Decimal(str(v if v not in (None, "") else 1)).quantize(RATE_Q, rounding=ROUND_HALF_UP)


class CurrencyService:
    @staticmethod
    def ensure_currency(*, workspace_id, code, name="", symbol="", decimal_places=2,
                        is_base=False, actor_id=None) -> Currency:
        cur, _ = Currency.objects.get_or_create(
            workspace_id=workspace_id, code=str(code).upper(),
            defaults={"name": name, "symbol": symbol, "decimal_places": decimal_places,
                      "is_base": is_base,
                      "created_by": uuid.UUID(str(actor_id)) if actor_id else None})
        return cur

    @staticmethod
    def set_base(*, workspace_id, code, actor_id=None) -> Currency:
        """Set the workspace base currency (idempotent; clears any prior base)."""
        code = str(code).upper()
        Currency.objects.filter(workspace_id=workspace_id, is_base=True).exclude(
            code=code).update(is_base=False)
        cur = CurrencyService.ensure_currency(workspace_id=workspace_id, code=code, is_base=True,
                                              actor_id=actor_id)
        if not cur.is_base:
            cur.is_base = True
            cur.save(update_fields=["is_base", "updated_at"])
        return cur

    @staticmethod
    def base_code(workspace_id) -> str:
        cur = Currency.objects.filter(workspace_id=workspace_id, is_base=True).first()
        return cur.code if cur else ""

    @staticmethod
    def set_rate(*, workspace_id, from_currency, to_currency, rate, rate_type="spot",
                 effective_date=None, actor_id=None) -> ExchangeRate:
        return ExchangeRate.objects.create(
            workspace_id=workspace_id, from_currency=str(from_currency).upper(),
            to_currency=str(to_currency).upper(), rate=_rate(rate), rate_type=rate_type,
            effective_date=effective_date,
            created_by=uuid.UUID(str(actor_id)) if actor_id else None)

    @staticmethod
    def get_rate(workspace_id, from_currency, to_currency, *, on_date=None,
                 rate_type=None) -> Decimal:
        """The rate to convert ``from_currency``→``to_currency`` on ``on_date`` (most recent effective
        rate on/before the date). Same currency → 1. Tries the inverse if no direct rate exists."""
        f, t = str(from_currency).upper(), str(to_currency).upper()
        if not f or not t or f == t:
            return Decimal("1")
        day = on_date or timezone.now().date()
        direct = CurrencyService._best(workspace_id, f, t, day, rate_type)
        if direct is not None:
            return direct
        inverse = CurrencyService._best(workspace_id, t, f, day, rate_type)
        if inverse is not None and inverse != 0:
            return (Decimal("1") / inverse).quantize(RATE_Q, rounding=ROUND_HALF_UP)
        raise CurrencyError(f"No exchange rate {f}->{t} on {day}.")

    @staticmethod
    def _best(workspace_id, f, t, day, rate_type):
        qs = ExchangeRate.objects.filter(
            workspace_id=workspace_id, from_currency=f, to_currency=t, is_active=True)
        if rate_type:
            qs = qs.filter(rate_type=rate_type)
        best = None
        for r in qs:
            if r.effective_date and r.effective_date > day:
                continue
            if best is None or (r.effective_date or _MIN) >= (best.effective_date or _MIN):
                best = r
        return _rate(best.rate) if best is not None else None

    @staticmethod
    def base_rate(workspace_id, currency, *, on_date=None) -> Decimal:
        """The rate to convert ``currency`` into the workspace base. 1 when no base is configured or
        the currency is blank/base — the backward-compatible default."""
        base = CurrencyService.base_code(workspace_id)
        cur = str(currency or "").upper()
        if not base or not cur or cur == base:
            return Decimal("1")
        return CurrencyService.get_rate(workspace_id, cur, base, on_date=on_date)

    @staticmethod
    def convert(workspace_id, amount, from_currency, to_currency, *, on_date=None) -> Decimal:
        rate = CurrencyService.get_rate(workspace_id, from_currency, to_currency, on_date=on_date)
        return (Decimal(str(amount or 0)) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_MIN = __import__("datetime").date.min
