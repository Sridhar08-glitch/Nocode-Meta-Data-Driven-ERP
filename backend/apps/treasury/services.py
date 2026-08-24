"""
Treasury services (Financial Platform — F12).

``InterestService``  — deterministic interest maths (fixed/floating, simple/compound/effective). No AI.
``TreasuryService``  — masters + every treasury EVENT as a ``TreasuryTransaction`` that posts ONLY
                       through ``GLBus`` (no parallel accounting).
``ScheduleService``  — interest / maturity / debt schedules as COMPUTED reports (from deal terms +
                       InterestService), NOT stored rows.
``LiquidityService`` — liquidity POSITION = Cash (F8) + investments − borrowings (computed).
``TreasuryForecastService`` — projected treasury cashflows (computed; reuses the platform).
Deals carry ``company_id`` (F11) + ``dimensions`` (F9); FX reuses Currency (F7).
"""
from __future__ import annotations

import calendar
import datetime as _dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .models import TreasuryFacility, TreasuryInvestment, TreasuryTransaction

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")
_PER_YEAR = {"monthly": 12, "quarterly": 4, "semi_annual": 2, "annual": 1, "bullet": 1}
_PERIOD_DAYS = {"monthly": 30, "quarterly": 91, "semi_annual": 182, "annual": 365, "bullet": 365}


class TreasuryError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _add_months(day, months):
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return _dt.date(year, month, min(day.day, last))


def _add_period(day, frequency, n):
    if frequency == "annual":
        return _add_months(day, 12 * n)
    return _add_months(day, {"monthly": 1, "quarterly": 3, "semi_annual": 6}.get(frequency, 1) * n)


class InterestService:
    """Deterministic interest maths — no AI."""

    @staticmethod
    def effective_rate(*, nominal_pct, periods_per_year) -> Decimal:
        n = Decimal(str(periods_per_year or 1))
        r = Decimal(str(nominal_pct)) / HUNDRED
        eff = (Decimal("1") + r / n) ** int(n) - Decimal("1")
        return (eff * HUNDRED).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def floating_rate(*, reference_rate_pct, spread_pct) -> Decimal:
        return (Decimal(str(reference_rate_pct or 0))
                + Decimal(str(spread_pct or 0))).quantize(Decimal("0.000001"))

    @staticmethod
    def simple_interest(*, principal, annual_rate_pct, days, day_count=365) -> Decimal:
        return _m(Decimal(str(principal)) * Decimal(str(annual_rate_pct)) / HUNDRED
                  * Decimal(str(days)) / Decimal(str(day_count or 365)))

    @staticmethod
    def compound_interest(*, principal, annual_rate_pct, years, periods_per_year=1) -> Decimal:
        p = Decimal(str(principal))
        r = Decimal(str(annual_rate_pct)) / HUNDRED
        n = Decimal(str(periods_per_year or 1))
        periods = int(n * Decimal(str(years)))
        return _m(p * (Decimal("1") + r / n) ** periods - p)

    @staticmethod
    def period_interest(*, principal, annual_rate_pct, frequency="monthly", day_count=365) -> Decimal:
        """Interest for ONE payment period of ``frequency`` on ``principal`` (simple, day-count based)."""
        return InterestService.simple_interest(
            principal=principal, annual_rate_pct=annual_rate_pct,
            days=_PERIOD_DAYS.get(frequency, 30), day_count=day_count)


def _accounts(workspace_id, actor_id=None):
    s = ensure_accounting_settings(workspace_id, actor_id=actor_id)
    return {"cash": "1010",
            "investment": getattr(s, "default_investment_account", "1250"),
            "borrowing": getattr(s, "default_borrowing_account", "2600"),
            "interest_expense": getattr(s, "default_interest_expense_account", "6500"),
            "interest_income": getattr(s, "default_interest_income_account", "4920")}


class TreasuryService:
    # ── masters ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _number(workspace_id, key, prefix, actor_id):
        from apps.numbering.services import NumberingService
        NumberingService.ensure_sequence(workspace_id, key,
                                         defaults={"prefix": prefix, "padding": 6},
                                         created_by=actor_id)
        return NumberingService.allocate(workspace_id, key, actor_id=actor_id,
                                         context={"source_module": "treasury", "source_ref": key})

    @staticmethod
    def create_facility(*, workspace_id, principal, facility_type="loan", counterparty_id=None,
                        currency="", interest_rate=0, rate_type="fixed", reference_rate="", spread=0,
                        compounding="simple", payment_frequency="monthly", start_date=None,
                        maturity_date=None, company_id=None, dimensions=None,
                        actor_id=None) -> TreasuryFacility:
        principal = _m(principal)
        if principal <= 0:
            raise TreasuryError("Facility principal must be positive.")
        number = TreasuryService._number(workspace_id, "treasury_facility", "BOR-", actor_id)
        return TreasuryFacility.objects.create(
            workspace_id=workspace_id, number=number, facility_type=facility_type,
            counterparty_id=counterparty_id, principal=principal, facility_limit=principal,
            outstanding=Decimal("0"), currency=currency, interest_rate=Decimal(str(interest_rate)),
            rate_type=rate_type, reference_rate=reference_rate, spread=Decimal(str(spread)),
            compounding=compounding, payment_frequency=payment_frequency, start_date=start_date,
            maturity_date=maturity_date, company_id=company_id, dimensions=dimensions or {},
            status=TreasuryFacility.ACTIVE, created_by=_uid(actor_id))

    @staticmethod
    def create_investment(*, workspace_id, principal, investment_type="deposit",
                          counterparty_id=None, currency="", interest_rate=0, rate_type="fixed",
                          compounding="simple", payment_frequency="monthly", start_date=None,
                          maturity_date=None, company_id=None, dimensions=None,
                          actor_id=None) -> TreasuryInvestment:
        principal = _m(principal)
        if principal <= 0:
            raise TreasuryError("Investment principal must be positive.")
        number = TreasuryService._number(workspace_id, "treasury_investment", "INV-", actor_id)
        return TreasuryInvestment.objects.create(
            workspace_id=workspace_id, number=number, investment_type=investment_type,
            counterparty_id=counterparty_id, principal=principal, face_value=principal,
            outstanding=principal, currency=currency, interest_rate=Decimal(str(interest_rate)),
            rate_type=rate_type, compounding=compounding, payment_frequency=payment_frequency,
            start_date=start_date, maturity_date=maturity_date, company_id=company_id,
            dimensions=dimensions or {}, status=TreasuryInvestment.ACTIVE, created_by=_uid(actor_id))

    # ── events (every one is a TreasuryTransaction posting via GLBus) ────────────
    @staticmethod
    def _txn(*, workspace_id, transaction_type, lines, amount, date, facility=None, investment=None,
             counterparty_id=None, company_id=None, dimensions=None, external_ref="",
             actor_id=None) -> TreasuryTransaction:
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        with transaction.atomic():
            if external_ref:
                dup = (TreasuryTransaction.objects.filter(
                    workspace_id=workspace_id, external_ref=external_ref)
                    .exclude(status=TreasuryTransaction.REVERSED).first())
                if dup is not None:
                    return dup
            number = TreasuryService._number(workspace_id, "treasury_transaction", "TXN-", actor_id)
            if dimensions:
                for ln in lines:
                    ln.setdefault("dimensions", dimensions)
            try:
                entry = GLBus.post(workspace_id, date=date or timezone.now().date(), lines=lines,
                                   memo=f"{transaction_type} {number}", source_module="treasury",
                                   source_ref=number, company_id=company_id, actor_id=actor_id)
            except LedgerError as exc:
                emit_post_failure(workspace_id, module="treasury", source_ref=number,
                                  error=str(exc), actor_id=actor_id)
                raise
            deal = facility or investment
            txn = TreasuryTransaction.objects.create(
                workspace_id=workspace_id, number=number, transaction_type=transaction_type,
                facility=facility, investment=investment, counterparty_id=counterparty_id,
                amount=_m(amount), currency=deal.currency if deal else "",
                value_date=date, company_id=company_id, dimensions=dimensions or {},
                external_ref=str(external_ref or ""), status=TreasuryTransaction.POSTED,
                journal_entry_id=entry.id if entry else None, created_by=_uid(actor_id))
        emit_event(workspace_id, "treasury_transaction", txn.id, f"treasury.{transaction_type}",
                   {"number": number, "amount": str(_m(amount))}, actor_id)
        return txn

    @staticmethod
    def drawdown(*, workspace_id, facility_id, amount=None, date=None, actor_id=None):
        with transaction.atomic():
            fac = (TreasuryFacility.objects.select_for_update()
                   .filter(workspace_id=workspace_id, id=facility_id).first())
            if fac is None:
                raise TreasuryError("Facility not found.")
            amt = _m(amount) if amount is not None else fac.principal
            acc = _accounts(workspace_id, actor_id)
            txn = TreasuryService._txn(
                workspace_id=workspace_id, transaction_type=TreasuryTransaction.DRAWDOWN,
                lines=[{"account_code": acc["cash"], "debit": str(amt)},
                       {"account_code": acc["borrowing"], "credit": str(amt)}],
                amount=amt, date=date or fac.start_date, facility=fac,
                counterparty_id=fac.counterparty_id, company_id=fac.company_id,
                dimensions=fac.dimensions, actor_id=actor_id)
            fac.drawn_amount = _m(fac.drawn_amount + amt)
            fac.outstanding = _m(fac.outstanding + amt)
            fac.save(update_fields=["drawn_amount", "outstanding", "updated_at"])
        return txn

    @staticmethod
    def place_investment(*, workspace_id, investment_id, date=None, actor_id=None):
        inv = TreasuryInvestment.objects.filter(workspace_id=workspace_id, id=investment_id).first()
        if inv is None:
            raise TreasuryError("Investment not found.")
        acc = _accounts(workspace_id, actor_id)
        return TreasuryService._txn(
            workspace_id=workspace_id, transaction_type=TreasuryTransaction.INVESTMENT_PURCHASE,
            lines=[{"account_code": acc["investment"], "debit": str(inv.principal)},
                   {"account_code": acc["cash"], "credit": str(inv.principal)}],
            amount=inv.principal, date=date or inv.start_date, investment=inv,
            counterparty_id=inv.counterparty_id, company_id=inv.company_id,
            dimensions=inv.dimensions, actor_id=actor_id)

    @staticmethod
    def pay_interest_due(*, workspace_id, as_of=None, actor_id=None) -> dict:
        """Post INTEREST_PAYMENT (facilities: Dr Expense/Cr Cash) + interest receipts (investments:
        Dr Cash/Cr Income) for every scheduled interest period due on/before ``as_of``. The schedule
        is COMPUTED from deal terms; idempotent per (deal, period) via external_ref."""
        as_of = as_of or timezone.now().date()
        acc = _accounts(workspace_id, actor_id)
        posted, total = 0, Decimal("0")
        for fac in TreasuryFacility.objects.filter(workspace_id=workspace_id,
                                                   status=TreasuryFacility.ACTIVE):
            posted, total = TreasuryService._pay_deal_interest(
                workspace_id, fac, "facility", as_of, acc, actor_id, posted, total)
        for inv in TreasuryInvestment.objects.filter(workspace_id=workspace_id,
                                                     status=TreasuryInvestment.ACTIVE):
            posted, total = TreasuryService._pay_deal_interest(
                workspace_id, inv, "investment", as_of, acc, actor_id, posted, total)
        return {"posted": posted, "total_interest": str(_m(total))}

    @staticmethod
    def _pay_deal_interest(workspace_id, deal, kind, as_of, acc, actor_id, posted, total):
        for row in ScheduleService.interest_schedule(workspace_id, kind, deal.id):
            if row["due_date"] > str(as_of):
                continue
            ext = f"{kind}:{deal.id}:int:{row['period_no']}"
            amt = Decimal(row["interest"])
            if amt <= 0:
                continue
            if kind == "facility":
                lines = [{"account_code": acc["interest_expense"], "debit": str(amt)},
                         {"account_code": acc["cash"], "credit": str(amt)}]
                ttype = TreasuryTransaction.INTEREST_PAYMENT
            else:
                lines = [{"account_code": acc["cash"], "debit": str(amt)},
                         {"account_code": acc["interest_income"], "credit": str(amt)}]
                ttype = TreasuryTransaction.COUPON
            before = TreasuryTransaction.objects.filter(
                workspace_id=workspace_id, external_ref=ext).exclude(
                status=TreasuryTransaction.REVERSED).exists()
            TreasuryService._txn(
                workspace_id=workspace_id, transaction_type=ttype, lines=lines, amount=amt,
                date=_dt.date.fromisoformat(row["due_date"]),
                facility=deal if kind == "facility" else None,
                investment=deal if kind == "investment" else None,
                counterparty_id=deal.counterparty_id, company_id=deal.company_id,
                dimensions=deal.dimensions, external_ref=ext, actor_id=actor_id)
            if not before:                        # count only genuinely new posts (idempotent re-runs skip)
                posted += 1
                total += amt
        return posted, total

    @staticmethod
    def repay_principal(*, workspace_id, facility_id, amount=None, date=None, actor_id=None):
        with transaction.atomic():
            fac = (TreasuryFacility.objects.select_for_update()
                   .filter(workspace_id=workspace_id, id=facility_id).first())
            if fac is None:
                raise TreasuryError("Facility not found.")
            amt = _m(amount) if amount is not None else fac.outstanding
            acc = _accounts(workspace_id, actor_id)
            txn = TreasuryService._txn(
                workspace_id=workspace_id, transaction_type=TreasuryTransaction.PRINCIPAL_REPAYMENT,
                lines=[{"account_code": acc["borrowing"], "debit": str(amt)},
                       {"account_code": acc["cash"], "credit": str(amt)}],
                amount=amt, date=date, facility=fac, counterparty_id=fac.counterparty_id,
                company_id=fac.company_id, dimensions=fac.dimensions, actor_id=actor_id)
            fac.outstanding = _m(fac.outstanding - amt)
            if fac.outstanding <= 0:
                fac.status = TreasuryFacility.REPAID
            fac.save(update_fields=["outstanding", "status", "updated_at"])
        return txn

    @staticmethod
    def mature_investment(*, workspace_id, investment_id, date=None, actor_id=None):
        with transaction.atomic():
            inv = (TreasuryInvestment.objects.select_for_update()
                   .filter(workspace_id=workspace_id, id=investment_id).first())
            if inv is None:
                raise TreasuryError("Investment not found.")
            acc = _accounts(workspace_id, actor_id)
            txn = TreasuryService._txn(
                workspace_id=workspace_id, transaction_type=TreasuryTransaction.MATURITY,
                lines=[{"account_code": acc["cash"], "debit": str(inv.principal)},
                       {"account_code": acc["investment"], "credit": str(inv.principal)}],
                amount=inv.principal, date=date, investment=inv,
                counterparty_id=inv.counterparty_id, company_id=inv.company_id,
                dimensions=inv.dimensions, actor_id=actor_id)
            inv.outstanding = Decimal("0")
            inv.status = TreasuryInvestment.MATURED
            inv.save(update_fields=["outstanding", "status", "updated_at"])
        return txn


class ScheduleService:
    """Interest / maturity / debt schedules — COMPUTED reports (no stored rows)."""

    @staticmethod
    def _deal(workspace_id, kind, deal_id):
        model = TreasuryFacility if kind == "facility" else TreasuryInvestment
        deal = model.objects.filter(workspace_id=workspace_id, id=deal_id).first()
        if deal is None:
            raise TreasuryError(f"{kind} not found.")
        return deal

    @staticmethod
    def interest_schedule(workspace_id, kind, deal_id) -> list:
        """Compute the interest schedule from the deal's terms — one row per payment period."""
        deal = ScheduleService._deal(workspace_id, kind, deal_id)
        freq = deal.payment_frequency
        start = deal.start_date or timezone.now().date()
        end = deal.maturity_date
        rate = (InterestService.floating_rate(reference_rate_pct=deal.reference_rate or 0,
                                              spread_pct=deal.spread)
                if deal.rate_type == "floating" else deal.interest_rate)
        rows = []
        if freq == "bullet" or not end:
            n = 1
        else:
            per_year = _PER_YEAR.get(freq, 12)
            months = max(1, (end.year - start.year) * 12 + (end.month - start.month))
            n = max(1, round(months / (12 / per_year)))
        for i in range(1, n + 1):
            interest = InterestService.period_interest(
                principal=deal.principal, annual_rate_pct=rate,
                frequency="annual" if freq == "bullet" else freq, day_count=deal.day_count)
            rows.append({"period_no": i, "due_date": str(_add_period(start, freq, i)),
                         "interest": str(interest), "principal": str(deal.principal)})
        return rows

    @staticmethod
    def debt_schedule(workspace_id) -> list:
        return [{"number": f.number, "facility_type": f.facility_type, "principal": str(f.principal),
                 "outstanding": str(f.outstanding), "rate": str(f.interest_rate),
                 "maturity_date": str(f.maturity_date) if f.maturity_date else None}
                for f in TreasuryFacility.objects.filter(
                    workspace_id=workspace_id, status=TreasuryFacility.ACTIVE).order_by("maturity_date")]

    @staticmethod
    def maturity_schedule(workspace_id) -> list:
        out = []
        for f in TreasuryFacility.objects.filter(workspace_id=workspace_id,
                                                 status=TreasuryFacility.ACTIVE):
            out.append({"kind": "facility", "number": f.number, "amount": str(f.outstanding),
                        "maturity_date": str(f.maturity_date) if f.maturity_date else None})
        for i in TreasuryInvestment.objects.filter(workspace_id=workspace_id,
                                                   status=TreasuryInvestment.ACTIVE):
            out.append({"kind": "investment", "number": i.number, "amount": str(i.outstanding),
                        "maturity_date": str(i.maturity_date) if i.maturity_date else None})
        return sorted(out, key=lambda r: r["maturity_date"] or "9999")


class LiquidityService:
    @staticmethod
    def position(workspace_id) -> dict:
        """Liquidity = Cash (reuse F8) + investments − borrowings. Balances are NOT re-stored."""
        from apps.cash.services import CashService
        cash = Decimal(CashService.cash_position(workspace_id)["total_available"])
        investments = sum((i.outstanding for i in TreasuryInvestment.objects.filter(
            workspace_id=workspace_id, status=TreasuryInvestment.ACTIVE)), Decimal("0"))
        borrowings = sum((f.outstanding for f in TreasuryFacility.objects.filter(
            workspace_id=workspace_id, status=TreasuryFacility.ACTIVE)), Decimal("0"))
        return {"cash": str(_m(cash)), "investments": str(_m(investments)),
                "borrowings": str(_m(borrowings)),
                "net_liquidity": str(_m(cash + investments - borrowings))}

    @staticmethod
    def counterparty_exposure(workspace_id) -> list:
        rows: dict = {}
        for i in TreasuryInvestment.objects.filter(
                workspace_id=workspace_id, status=TreasuryInvestment.ACTIVE,
                counterparty__isnull=False).select_related("counterparty"):
            rows.setdefault(i.counterparty.code, [i.counterparty.exposure_limit, Decimal("0")])
            rows[i.counterparty.code][1] += i.outstanding
        return [{"counterparty": k, "limit": str(_m(v[0])), "exposure": str(_m(v[1]))}
                for k, v in sorted(rows.items())]


class TreasuryForecastService:
    @staticmethod
    def forecast(workspace_id, *, from_date=None, to_date=None) -> dict:
        """Projected treasury cashflows — COMPUTED from the interest schedules + maturities of active
        deals (reuses the platform; no duplicate forecasting engine)."""
        inflow, outflow = Decimal("0"), Decimal("0")
        for f in TreasuryFacility.objects.filter(workspace_id=workspace_id,
                                                 status=TreasuryFacility.ACTIVE):
            for row in ScheduleService.interest_schedule(workspace_id, "facility", f.id):
                if _in_window(row["due_date"], from_date, to_date):
                    outflow += Decimal(row["interest"])
            if _in_window(str(f.maturity_date), from_date, to_date):
                outflow += f.outstanding
        for i in TreasuryInvestment.objects.filter(workspace_id=workspace_id,
                                                   status=TreasuryInvestment.ACTIVE):
            for row in ScheduleService.interest_schedule(workspace_id, "investment", i.id):
                if _in_window(row["due_date"], from_date, to_date):
                    inflow += Decimal(row["interest"])
            if _in_window(str(i.maturity_date), from_date, to_date):
                inflow += i.outstanding
        opening = Decimal(LiquidityService.position(workspace_id)["net_liquidity"])
        return {"from": str(from_date) if from_date else None,
                "to": str(to_date) if to_date else None,
                "opening_liquidity": str(_m(opening)), "projected_inflows": str(_m(inflow)),
                "projected_outflows": str(_m(outflow)), "net_projected": str(_m(inflow - outflow)),
                "closing_liquidity": str(_m(opening + inflow - outflow))}


def _in_window(day_str, from_date, to_date) -> bool:
    if not day_str or day_str in ("None", "9999"):
        return False
    if from_date and day_str < str(from_date):
        return False
    return not (to_date and day_str > str(to_date))
