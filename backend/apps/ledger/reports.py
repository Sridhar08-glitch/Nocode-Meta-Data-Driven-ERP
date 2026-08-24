"""
Financial reports (Phase P2.3) — Trial Balance, General Ledger, Profit & Loss, Balance Sheet.

All reports are derived purely from POSTED (and REVERSED — their lines remain on the books,
offset by the reversing entry) journal lines. Balances are computed with DB-side aggregation;
no figure is ever stored, so reports can never drift from the ledger.

Sign convention: a raw account balance is ``debit − credit``. Asset/expense accounts are
debit-normal (positive balance = a debit); liability/equity/revenue are credit-normal, so their
"natural" presentation negates the raw balance.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce

from .models import (
    ASSET,
    EQUITY,
    EXPENSE,
    LIABILITY,
    REVENUE,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)

CENTS = Decimal("0.01")
_ZERO = Decimal("0.00")
_POSTED = [JournalEntry.POSTED, JournalEntry.REVERSED]


def _q(v) -> Decimal:
    return (v or _ZERO).quantize(CENTS)


def _line_qs(workspace_id, *, date_from=None, date_to=None, company_id=None):
    qs = JournalLine.objects.filter(workspace_id=workspace_id, entry__status__in=_POSTED)
    if date_from:
        qs = qs.filter(entry__date__gte=date_from)
    if date_to:
        qs = qs.filter(entry__date__lte=date_to)
    # F11 — legal-entity filter; omitted → whole workspace (single-company byte-identical). Kept in
    # sync with financial_reports._line_qs so the two statement engines agree under multi-company.
    if company_id is not None:
        qs = qs.filter(entry__company_id=company_id)
    return qs


def _balances_by_account(workspace_id, *, date_from=None, date_to=None) -> dict:
    """Map ``account_id -> {"debit", "credit", "balance"}`` (balance = debit − credit)."""
    dec = DecimalField(max_digits=20, decimal_places=2)
    rows = (_line_qs(workspace_id, date_from=date_from, date_to=date_to)
            .values("account_id")
            .annotate(debit=Coalesce(Sum("debit"), _ZERO, output_field=dec),
                      credit=Coalesce(Sum("credit"), _ZERO, output_field=dec)))
    out = {}
    for r in rows:
        d, c = _q(r["debit"]), _q(r["credit"])
        out[r["account_id"]] = {"debit": d, "credit": c, "balance": d - c}
    return out


def _accounts(workspace_id) -> dict:
    return {a.id: a for a in LedgerAccount.objects.filter(workspace_id=workspace_id)}


# ── Trial Balance ─────────────────────────────────────────────────────────────
def trial_balance(workspace_id, *, as_of=None) -> dict:
    bals = _balances_by_account(workspace_id, date_to=as_of)
    accts = _accounts(workspace_id)
    rows, total_d, total_c = [], _ZERO, _ZERO
    for acct_id, b in bals.items():
        acct = accts.get(acct_id)
        if acct is None:
            continue
        bal = b["balance"]
        debit = bal if bal > 0 else _ZERO
        credit = -bal if bal < 0 else _ZERO
        if debit == 0 and credit == 0:
            continue
        total_d += debit
        total_c += credit
        rows.append({"account_id": str(acct_id), "code": acct.code, "name": acct.name,
                     "account_type": acct.account_type, "debit": str(debit), "credit": str(credit)})
    rows.sort(key=lambda r: r["code"])
    return {"as_of": str(as_of) if as_of else None, "rows": rows,
            "total_debit": str(_q(total_d)), "total_credit": str(_q(total_c)),
            "balanced": _q(total_d) == _q(total_c)}


# ── General Ledger (account activity) ────────────────────────────────────────────
def general_ledger(workspace_id, account_id, *, date_from=None, date_to=None) -> dict:
    accts = _accounts(workspace_id)
    acct = accts.get(account_id)
    if acct is None:
        # account_id may arrive as a string from the query layer
        acct = next((a for a in accts.values() if str(a.id) == str(account_id)), None)
    if acct is None:
        return {"account": None, "opening_balance": "0.00", "lines": [], "closing_balance": "0.00"}

    opening = _ZERO
    if date_from:
        prior = (_line_qs(workspace_id, date_to=None)
                 .filter(account_id=acct.id, entry__date__lt=date_from)
                 .aggregate(d=Coalesce(Sum("debit"), _ZERO), c=Coalesce(Sum("credit"), _ZERO)))
        opening = _q(prior["d"]) - _q(prior["c"])

    qs = (_line_qs(workspace_id, date_from=date_from, date_to=date_to)
          .filter(account_id=acct.id)
          .select_related("entry").order_by("entry__date", "entry__created_at", "line_no"))
    running = opening
    lines = []
    for line_ in qs:
        running += _q(line_.debit) - _q(line_.credit)
        lines.append({"date": str(line_.entry.date), "entry_number": line_.entry.entry_number,
                      "memo": line_.memo or line_.entry.memo, "debit": str(_q(line_.debit)),
                      "credit": str(_q(line_.credit)), "balance": str(_q(running))})
    return {"account": {"id": str(acct.id), "code": acct.code, "name": acct.name,
                        "account_type": acct.account_type},
            "opening_balance": str(_q(opening)), "lines": lines,
            "closing_balance": str(_q(running))}


# ── Profit & Loss ─────────────────────────────────────────────────────────────
def profit_and_loss(workspace_id, *, date_from=None, date_to=None) -> dict:
    bals = _balances_by_account(workspace_id, date_from=date_from, date_to=date_to)
    accts = _accounts(workspace_id)
    revenue, expense = [], []
    total_rev, total_exp = _ZERO, _ZERO
    for acct_id, b in bals.items():
        acct = accts.get(acct_id)
        if acct is None:
            continue
        if acct.account_type == REVENUE:
            amount = -b["balance"]  # credit-normal → income is the negative of (debit−credit)
            total_rev += amount
            revenue.append({"code": acct.code, "name": acct.name, "amount": str(_q(amount))})
        elif acct.account_type == EXPENSE:
            amount = b["balance"]   # debit-normal
            total_exp += amount
            expense.append({"code": acct.code, "name": acct.name, "amount": str(_q(amount))})
    revenue.sort(key=lambda r: r["code"])
    expense.sort(key=lambda r: r["code"])
    net = _q(total_rev) - _q(total_exp)
    return {"date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "revenue": revenue, "expense": expense,
            "total_revenue": str(_q(total_rev)), "total_expense": str(_q(total_exp)),
            "net_income": str(net)}


# ── Balance Sheet ─────────────────────────────────────────────────────────────
def balance_sheet(workspace_id, *, as_of=None) -> dict:
    bals = _balances_by_account(workspace_id, date_to=as_of)
    accts = _accounts(workspace_id)
    assets, liabilities, equity = [], [], []
    total_assets, total_liab, total_equity = _ZERO, _ZERO, _ZERO
    net_income = _ZERO
    for acct_id, b in bals.items():
        acct = accts.get(acct_id)
        if acct is None:
            continue
        bal = b["balance"]
        if acct.account_type == ASSET:
            total_assets += bal
            assets.append({"code": acct.code, "name": acct.name, "amount": str(_q(bal))})
        elif acct.account_type == LIABILITY:
            total_liab += -bal
            liabilities.append({"code": acct.code, "name": acct.name, "amount": str(_q(-bal))})
        elif acct.account_type == EQUITY:
            total_equity += -bal
            equity.append({"code": acct.code, "name": acct.name, "amount": str(_q(-bal))})
        elif acct.account_type in (REVENUE, EXPENSE):
            # Net income = −(sum of nominal balances): revenue (credit, bal<0) adds, expense
            # (debit, bal>0) subtracts. Uniform −bal handles both correctly.
            net_income += -bal
    # Current-period earnings are not yet closed to retained earnings → show on the equity side.
    equity.append({"code": "—", "name": "Current earnings", "amount": str(_q(net_income))})
    total_equity += net_income
    assets.sort(key=lambda r: r["code"])
    liabilities.sort(key=lambda r: r["code"])
    eq_total = _q(total_equity)
    liab_total = _q(total_liab)
    asset_total = _q(total_assets)
    return {"as_of": str(as_of) if as_of else None,
            "assets": assets, "liabilities": liabilities, "equity": equity,
            "total_assets": str(asset_total), "total_liabilities": str(liab_total),
            "total_equity": str(eq_total),
            "total_liabilities_equity": str(_q(liab_total + eq_total)),
            "balanced": asset_total == _q(liab_total + eq_total)}
