"""
Chart-of-accounts seeding + fiscal-period generation (Phase P2.3).

A fresh workspace gets a ready-to-use accounting setup with NO manual account creation — the
master-prompt goal. ``seed_standard_chart`` provisions a conventional small-business chart;
``generate_fiscal_year`` creates the 12 monthly posting periods. Both are idempotent (existing
codes/periods are skipped) so they are safe to re-run.
"""
from __future__ import annotations

import calendar
import datetime as dt

from .models import AccountingPeriod, LedgerAccount

# (code, name, type). Conventional numbering: 1=assets 2=liabilities 3=equity 4=revenue 5/6=expense.
# This chart MUST cover every account the native finance modules post to (inventory, procurement,
# payroll, assets, manufacturing, projects) — see ACCOUNT_DEFAULTS below.
STANDARD_CHART = [
    ("1000", "Cash", "asset"),
    ("1010", "Bank", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Inventory", "asset"),
    ("1300", "Prepaid Expenses", "asset"),
    ("1450", "Input Tax Recoverable", "asset"),     # tax engine — recoverable input VAT/GST
    ("1400", "Finished Goods", "asset"),            # manufacturing FG receipt
    ("1500", "Fixed Assets", "asset"),
    ("1600", "Accumulated Depreciation", "asset"),  # contra-asset (assets module)
    ("1700", "Work In Progress", "asset"),          # manufacturing/projects WIP
    ("1250", "Short-Term Investments", "asset"),    # F12 treasury — deposits/MMF/bonds placed
    ("1900", "Intercompany Receivable", "asset"),   # F11 — due from group companies
    ("2000", "Accounts Payable", "liability"),
    ("2050", "Goods Received Not Invoiced", "liability"),  # procurement GR↔bill clearing
    ("2100", "Accrued Liabilities", "liability"),
    ("2200", "Taxes Payable", "liability"),
    ("2210", "Output Tax Payable", "liability"),     # tax engine — collected output VAT/GST
    ("2300", "Wages Payable", "liability"),
    ("2400", "Unearned Revenue", "liability"),
    ("2600", "Borrowings", "liability"),             # F12 treasury — loans/facilities drawn
    ("2900", "Intercompany Payable", "liability"),   # F11 — due to group companies
    ("3000", "Owner's Equity", "equity"),
    ("3100", "Retained Earnings", "equity"),
    ("3900", "Cumulative Translation Adjustment", "equity"),  # F11 — consolidation CTA reserve
    ("4000", "Sales Revenue", "revenue"),
    ("4100", "Service Revenue", "revenue"),
    ("4200", "Discounts & Allowances", "revenue"),   # contra-revenue (credit engine: discounts/credit notes)
    ("4900", "Other Income", "revenue"),             # late-fee / interest income (collections engine)
    ("4920", "Interest Income", "revenue"),          # F12 treasury — investment coupons/interest earned
    ("4930", "Foreign Exchange Gain", "revenue"),    # multi-currency: realized + unrealized FX gain
    ("5000", "Cost of Goods Sold", "expense"),
    ("6000", "Salaries & Wages", "expense"),
    ("6100", "Rent", "expense"),
    ("6200", "Utilities", "expense"),
    ("6300", "Depreciation Expense", "expense"),
    ("6400", "Office Supplies", "expense"),
    ("6500", "Interest Expense", "expense"),            # F12 treasury — borrowing interest paid
    ("6700", "Scholarships & Concessions", "expense"),  # credit engine: funded scholarships/waivers
    ("6800", "Bad Debt Expense", "expense"),            # credit engine: write-offs
    ("6960", "Foreign Exchange Loss", "expense"),       # multi-currency: realized + unrealized FX loss
    ("6900", "Other Expense", "expense"),
]

# Canonical account mapping: business-meaning → chart code. ``AccountingSettings`` is seeded from
# this, and the finance services resolve the codes they post to through it (no hardcoded codes in
# business logic — see PROJECT_HANDBOOK.md P2.15 remediation, Blocker 2).
ACCOUNT_DEFAULTS = {
    "default_cash_account": "1000",
    "default_receivable_account": "1100",
    "default_inventory_account": "1200",
    "default_finished_goods_account": "1400",
    "default_fixed_asset_account": "1500",
    "default_accumulated_depreciation_account": "1600",
    "default_wip_account": "1700",
    "default_payable_account": "2000",
    "default_grni_account": "2050",
    "default_revenue_account": "4000",
    "default_cogs_account": "5000",
    "default_depreciation_expense_account": "6300",
    # Credit engine (F3) — contra-revenue for discounts/credit notes, expense for
    # scholarships/waivers, expense for write-offs, revenue account refunds reduce.
    "default_discount_account": "4200",
    "default_scholarship_account": "6700",
    "default_writeoff_account": "6800",
    "default_refund_account": "4100",
    # Collections engine (F2) — late-fee / interest income.
    "default_late_fee_income_account": "4900",
    # Tax engine (G1) — output tax liability (collected) + recoverable input tax asset (paid).
    "default_output_tax_account": "2210",
    "default_input_tax_account": "1450",
    # Multi-currency — realized + unrealized foreign-exchange gain / loss.
    "default_fx_gain_account": "4930",
    "default_fx_loss_account": "6960",
    # Multi-company / consolidation (F11) — intercompany control + CTA reserve.
    "default_ic_receivable_account": "1900",
    "default_ic_payable_account": "2900",
    "default_cta_account": "3900",
    # Treasury (F12) — investments placed, borrowings drawn, interest earned/paid.
    "default_investment_account": "1250",
    "default_borrowing_account": "2600",
    "default_interest_income_account": "4920",
    "default_interest_expense_account": "6500",
}


def seed_standard_chart(workspace_id, *, created_by=None) -> dict:
    """Create any missing standard accounts. Returns ``{"created": n, "skipped": m}``."""
    existing = set(LedgerAccount.objects.filter(workspace_id=workspace_id)
                   .values_list("code", flat=True))
    created = 0
    to_create = []
    for code, name, atype in STANDARD_CHART:
        if code in existing:
            continue
        to_create.append(LedgerAccount(
            workspace_id=workspace_id, code=code, name=name, account_type=atype,
            created_by=created_by))
        created += 1
    LedgerAccount.objects.bulk_create(to_create)
    return {"created": created, "skipped": len(STANDARD_CHART) - created}


def generate_fiscal_year(workspace_id, *, year: int, start_month: int = 1) -> dict:
    """Create the 12 monthly periods of a fiscal year starting at ``start_month``. Period codes
    are ``YYYY-MM``; the fiscal_year label is the starting calendar year. Idempotent per code."""
    if not (1 <= start_month <= 12):
        start_month = 1
    existing = set(AccountingPeriod.objects.filter(workspace_id=workspace_id)
                   .values_list("code", flat=True))
    fy_label = f"FY{year}"
    created = 0
    month, y = start_month, year
    to_create = []
    for _ in range(12):
        last_day = calendar.monthrange(y, month)[1]
        code = f"{y:04d}-{month:02d}"
        if code not in existing:
            to_create.append(AccountingPeriod(
                workspace_id=workspace_id, code=code,
                name=dt.date(y, month, 1).strftime("%B %Y"),
                start_date=dt.date(y, month, 1), end_date=dt.date(y, month, last_day),
                status=AccountingPeriod.OPEN, fiscal_year=fy_label))
            created += 1
        month += 1
        if month > 12:
            month, y = 1, y + 1
    AccountingPeriod.objects.bulk_create(to_create)
    return {"created": created, "skipped": 12 - created, "fiscal_year": fy_label}
