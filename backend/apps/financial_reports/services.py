"""
Financial Statements engine (Financial Platform — F6 / Gaps G6 + G8).

``StatementService`` produces the standard financial statements — Trial Balance, Balance Sheet,
Profit & Loss, Cash-Flow (movement), General Ledger detail, and AR/AP Aging — as PURE READS over the
single GL (``apps.ledger``). It owns NO new accounting: every figure is derived from posted
``JournalLine`` rows (POSTED + REVERSED, since a reversed entry really hit the books and is cancelled
by its reversing entry). Package-independent — every ERP package's postings appear here automatically
because they all post through ``GLBus``. Workspace-scoped (RLS applies to the underlying ledger tables).
"""
from __future__ import annotations

import datetime as _dt
from decimal import ROUND_HALF_UP, Decimal

from apps.ledger.models import (
    ASSET,
    EQUITY,
    EXPENSE,
    LIABILITY,
    REVENUE,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)
from apps.ledger.provisioning import ensure_accounting_settings

CENTS = Decimal("0.01")
_POSTED = [JournalEntry.POSTED, JournalEntry.REVERSED]


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _s(v) -> str:
    return str(_m(v))


class StatementService:
    # ── shared aggregation ──────────────────────────────────────────────────────
    @staticmethod
    def _accounts(workspace_id) -> dict:
        return {a.id: a for a in LedgerAccount.objects.filter(workspace_id=workspace_id)}

    @staticmethod
    def _line_qs(workspace_id, *, from_date=None, to_date=None, dimensions=None, company_id=None):
        qs = JournalLine.objects.filter(
            workspace_id=workspace_id, entry__status__in=_POSTED)
        if from_date:
            qs = qs.filter(entry__date__gte=from_date)
        if to_date:
            qs = qs.filter(entry__date__lte=to_date)
        # F11 — legal-entity filter; omitted → whole workspace (single-company byte-identical).
        if company_id is not None:
            qs = qs.filter(entry__company_id=company_id)
        # F9 — dimension filter: {dimension_code: value_code}; a line matches when its dimensions map
        # contains every requested pair. Legacy callers pass no dimensions → no filter.
        for dcode, vcode in (dimensions or {}).items():
            qs = qs.filter(**{f"dimensions__{dcode}": vcode})
        return qs

    @staticmethod
    def _totals_by_account(workspace_id, *, from_date=None, to_date=None, dimensions=None,
                           company_id=None) -> dict:
        """{account_id: {"debit": D, "credit": D}} over posted lines in the window, in the BASE
        currency (base_* == transaction amount for single-currency workspaces)."""
        out: dict = {}
        for ln in StatementService._line_qs(
                workspace_id, from_date=from_date, to_date=to_date, dimensions=dimensions,
                company_id=company_id).values("account_id", "base_debit", "base_credit"):
            slot = out.setdefault(ln["account_id"], {"debit": Decimal("0"), "credit": Decimal("0")})
            slot["debit"] += ln["base_debit"]
            slot["credit"] += ln["base_credit"]
        return out

    # ── Trial Balance ───────────────────────────────────────────────────────────
    @staticmethod
    def trial_balance(workspace_id, *, as_of=None, dimensions=None, company_id=None) -> dict:
        accts = StatementService._accounts(workspace_id)
        totals = StatementService._totals_by_account(workspace_id, to_date=as_of,
                                                     dimensions=dimensions, company_id=company_id)
        rows, td, tc = [], Decimal("0"), Decimal("0")
        for aid, t in totals.items():
            acct = accts.get(aid)
            if acct is None:
                continue
            bal = t["debit"] - t["credit"]
            debit = bal if bal > 0 else Decimal("0")
            credit = -bal if bal < 0 else Decimal("0")
            td += debit
            tc += credit
            rows.append({"code": acct.code, "name": acct.name, "type": acct.account_type,
                         "debit": _s(debit), "credit": _s(credit)})
        rows.sort(key=lambda r: r["code"])
        return {"as_of": str(as_of) if as_of else None, "rows": rows,
                "total_debit": _s(td), "total_credit": _s(tc), "balanced": _m(td) == _m(tc)}

    # ── Profit & Loss ───────────────────────────────────────────────────────────
    @staticmethod
    def profit_and_loss(workspace_id, *, from_date=None, to_date=None, dimensions=None,
                        company_id=None) -> dict:
        accts = StatementService._accounts(workspace_id)
        totals = StatementService._totals_by_account(
            workspace_id, from_date=from_date, to_date=to_date, dimensions=dimensions,
            company_id=company_id)
        revenue, expense = [], []
        rev_total, exp_total = Decimal("0"), Decimal("0")
        for aid, t in totals.items():
            acct = accts.get(aid)
            if acct is None:
                continue
            if acct.account_type == REVENUE:
                amt = t["credit"] - t["debit"]         # revenue is credit-normal
                rev_total += amt
                revenue.append({"code": acct.code, "name": acct.name, "amount": _s(amt)})
            elif acct.account_type == EXPENSE:
                amt = t["debit"] - t["credit"]          # expense is debit-normal
                exp_total += amt
                expense.append({"code": acct.code, "name": acct.name, "amount": _s(amt)})
        revenue.sort(key=lambda r: r["code"])
        expense.sort(key=lambda r: r["code"])
        return {"from": str(from_date) if from_date else None,
                "to": str(to_date) if to_date else None,
                "revenue": revenue, "expenses": expense,
                "total_revenue": _s(rev_total), "total_expenses": _s(exp_total),
                "net_income": _s(rev_total - exp_total)}

    # ── Dimension P&L (segment report) ──────────────────────────────────────────
    @staticmethod
    def dimension_pnl(workspace_id, *, dimension_code, from_date=None, to_date=None) -> dict:
        """P&L grouped by each value of a dimension (segment reporting) — reuses ``profit_and_loss``
        filtered per value. Reports the actual dimension values present (lines with no value for the
        dimension are simply not part of any segment)."""
        values = set()
        for ln in StatementService._line_qs(
                workspace_id, from_date=from_date, to_date=to_date).values_list(
                "dimensions", flat=True):
            v = (ln or {}).get(dimension_code)
            if v:
                values.add(v)
        rows = []
        for v in sorted(values):
            pnl = StatementService.profit_and_loss(
                workspace_id, from_date=from_date, to_date=to_date, dimensions={dimension_code: v})
            rows.append({"value": v, "total_revenue": pnl["total_revenue"],
                         "total_expenses": pnl["total_expenses"], "net_income": pnl["net_income"]})
        return {"dimension": dimension_code, "from": str(from_date) if from_date else None,
                "to": str(to_date) if to_date else None, "segments": rows}

    # ── Balance Sheet ───────────────────────────────────────────────────────────
    @staticmethod
    def balance_sheet(workspace_id, *, as_of=None, dimensions=None, company_id=None) -> dict:
        accts = StatementService._accounts(workspace_id)
        totals = StatementService._totals_by_account(workspace_id, to_date=as_of,
                                                     dimensions=dimensions, company_id=company_id)
        assets, liabilities, equity = [], [], []
        a_tot, l_tot, e_tot = Decimal("0"), Decimal("0"), Decimal("0")
        net_income = Decimal("0")
        for aid, t in totals.items():
            acct = accts.get(aid)
            if acct is None:
                continue
            debit_bal = t["debit"] - t["credit"]
            credit_bal = -debit_bal
            if acct.account_type == ASSET:
                a_tot += debit_bal
                assets.append({"code": acct.code, "name": acct.name, "amount": _s(debit_bal)})
            elif acct.account_type == LIABILITY:
                l_tot += credit_bal
                liabilities.append({"code": acct.code, "name": acct.name, "amount": _s(credit_bal)})
            elif acct.account_type == EQUITY:
                e_tot += credit_bal
                equity.append({"code": acct.code, "name": acct.name, "amount": _s(credit_bal)})
            elif acct.account_type == REVENUE:
                net_income += (t["credit"] - t["debit"])
            elif acct.account_type == EXPENSE:
                net_income -= (t["debit"] - t["credit"])
        # Current-period earnings roll into equity (retained-earnings not yet closed).
        equity.append({"code": "NI", "name": "Current Earnings", "amount": _s(net_income)})
        e_tot += net_income
        for section in (assets, liabilities, equity):
            section.sort(key=lambda r: r["code"])
        return {"as_of": str(as_of) if as_of else None,
                "assets": assets, "liabilities": liabilities, "equity": equity,
                "total_assets": _s(a_tot), "total_liabilities": _s(l_tot),
                "total_equity": _s(e_tot),
                "balanced": _m(a_tot) == _m(l_tot + e_tot)}

    # ── Cash-Flow (movement on cash/bank accounts — direct) ─────────────────────
    @staticmethod
    def cash_flow(workspace_id, *, from_date=None, to_date=None) -> dict:
        settings = ensure_accounting_settings(workspace_id)
        cash_codes = {settings.default_cash_account, "1010"}       # cash + bank
        accts = {a.code: a for a in LedgerAccount.objects.filter(
            workspace_id=workspace_id, code__in=cash_codes)}
        cash_ids = {a.id for a in accts.values()}
        opening = Decimal("0")
        if from_date:
            for ln in StatementService._line_qs(workspace_id, to_date=_prev_day(from_date)).filter(
                    account_id__in=cash_ids).values("base_debit", "base_credit"):
                opening += ln["base_debit"] - ln["base_credit"]
        inflow, outflow = Decimal("0"), Decimal("0")
        for ln in StatementService._line_qs(
                workspace_id, from_date=from_date, to_date=to_date).filter(
                account_id__in=cash_ids).values("base_debit", "base_credit"):
            inflow += ln["base_debit"]
            outflow += ln["base_credit"]
        net = inflow - outflow
        return {"from": str(from_date) if from_date else None,
                "to": str(to_date) if to_date else None,
                "opening_cash": _s(opening), "inflows": _s(inflow), "outflows": _s(outflow),
                "net_change": _s(net), "closing_cash": _s(opening + net),
                "method": "direct (cash-account movement)"}

    # ── General Ledger detail (one account, running balance) ────────────────────
    @staticmethod
    def general_ledger(workspace_id, *, account_code, from_date=None, to_date=None) -> dict:
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=str(account_code)).first()
        if acct is None:
            return {"account": account_code, "rows": [], "error": "unknown account"}
        opening = Decimal("0")
        if from_date:
            for ln in StatementService._line_qs(
                    workspace_id, to_date=_prev_day(from_date)).filter(
                    account_id=acct.id).values("base_debit", "base_credit"):
                opening += ln["base_debit"] - ln["base_credit"]
        rows, running = [], opening
        qs = (StatementService._line_qs(workspace_id, from_date=from_date, to_date=to_date)
              .filter(account_id=acct.id).select_related("entry")
              .order_by("entry__date", "entry__entry_number", "line_no"))
        for ln in qs:
            running += ln.base_debit - ln.base_credit
            rows.append({"date": str(ln.entry.date), "entry": ln.entry.entry_number,
                         "memo": ln.memo or ln.entry.memo, "partner_ref": ln.partner_ref,
                         "debit": _s(ln.base_debit), "credit": _s(ln.base_credit),
                         "balance": _s(running)})
        return {"account": acct.code, "name": acct.name, "opening_balance": _s(opening),
                "rows": rows, "closing_balance": _s(running)}

    # ── AR / AP Aging ───────────────────────────────────────────────────────────
    # NOTE (documented limitation): aging is LINE-LEVEL — each open sub-ledger line is bucketed by
    # its OWN posting date. True invoice↔payment matching (a payment ageing with the invoice it
    # settles) needs the Settlement/Allocation engine, which is not yet built; per-partner TOTALS are
    # exact, but a partial payment ages independently of its invoice until settlement lands.
    @staticmethod
    def _aging(workspace_id, account_code, *, as_of=None, buckets=(30, 60, 90)) -> dict:
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=str(account_code)).first()
        as_of = as_of or _dt.date.today()  # noqa: DTZ011 — a report as-of date, not a timestamp
        labels = ["current", *[f"{b}+" for b in buckets]]
        partners: dict = {}
        if acct is not None:
            qs = (StatementService._line_qs(workspace_id, to_date=as_of)
                  .filter(account_id=acct.id).select_related("entry")
                  .values("partner_ref", "base_debit", "base_credit", "entry__date"))
            for ln in qs:
                p = ln["partner_ref"] or "(unassigned)"
                slot = partners.setdefault(p, {label_: Decimal("0") for label_ in labels})
                bal = ln["base_debit"] - ln["base_credit"]   # receivable: debit-normal (base ccy)
                age = (as_of - ln["entry__date"]).days
                bucket = "current"
                for b in buckets:
                    if age >= b:
                        bucket = f"{b}+"
                slot[bucket] += bal
        rows, totals = [], {label_: Decimal("0") for label_ in labels}
        grand = Decimal("0")
        for partner, slot in partners.items():
            total = sum(slot.values(), Decimal("0"))
            if _m(total) == 0:
                continue
            grand += total
            for label_ in labels:
                totals[label_] += slot[label_]
            rows.append({"partner_ref": partner, "total": _s(total),
                         **{label_: _s(slot[label_]) for label_ in labels}})
        rows.sort(key=lambda r: r["partner_ref"])
        return {"as_of": str(as_of), "buckets": labels, "rows": rows,
                "totals": {label_: _s(totals[label_]) for label_ in labels}, "grand_total": _s(grand)}

    @staticmethod
    def ar_aging(workspace_id, *, as_of=None, buckets=(30, 60, 90)) -> dict:
        settings = ensure_accounting_settings(workspace_id)
        return StatementService._aging(
            workspace_id, settings.default_receivable_account, as_of=as_of, buckets=buckets)

    @staticmethod
    def ap_aging(workspace_id, *, as_of=None, buckets=(30, 60, 90)) -> dict:
        settings = ensure_accounting_settings(workspace_id)
        out = StatementService._aging(
            workspace_id, settings.default_payable_account, as_of=as_of, buckets=buckets)
        # payables are credit-normal — flip the sign so amounts read positive
        for r in out["rows"]:
            for k in ("total", *out["buckets"]):
                r[k] = _s(-Decimal(r[k]))
        for k in out["buckets"]:
            out["totals"][k] = _s(-Decimal(out["totals"][k]))
        out["grand_total"] = _s(-Decimal(out["grand_total"]))
        return out


def _prev_day(d):
    return d - _dt.timedelta(days=1)
