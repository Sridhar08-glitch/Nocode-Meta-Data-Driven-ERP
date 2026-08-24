"""
Financial KPI Library catalog (F13) — the single declaration of every standard finance KPI, with the
AI-READINESS metadata mandated by governance (name / formula / inputs / dependencies / unit / trend
direction / thresholds / category / explanation) so an assistant can EXPLAIN a KPI value without
reimplementing the business logic (§2: this is descriptive metadata, NOT an AI feature).

Each entry drives BOTH the seeded `analytics.KPIDefinition` (code / name / unit / direction /
target+thresholds / description) AND the `/financial-kpis/catalog/` API. `native_key = finance_<code>`
resolves to the evaluator in `evaluators.py`. `category` here is the FINE finance category (liquidity,
profitability, …); the seeded KPIDefinition.category is "financial" so the KPIs integrate with the
existing CFO/CEO scorecards. Every KPI reuses an existing platform (`dependencies`) — F13 owns none of
the accounting.
"""
from __future__ import annotations

# code, name, category, unit, direction, target, warning, formula, inputs, dependencies, explanation
K = "financial"

_CATALOG = [
    # ── Liquidity ────────────────────────────────────────────────────────────────
    ("current_ratio", "Current Ratio", "liquidity", "x", "higher_better", 2, 1.5,
     "current_assets / current_liabilities", ["current_assets", "current_liabilities"],
     ["StatementService.balance_sheet"],
     "Ability to cover short-term obligations with short-term assets. >2 healthy, <1 a red flag."),
    ("quick_ratio", "Quick Ratio (Acid Test)", "liquidity", "x", "higher_better", 1, 0.8,
     "(current_assets - inventory) / current_liabilities",
     ["current_assets", "inventory", "current_liabilities"], ["StatementService.balance_sheet"],
     "Liquidity excluding inventory — the sternest short-term solvency test."),
    ("cash_ratio", "Cash Ratio", "liquidity", "x", "higher_better", 0.5, 0.2,
     "(cash + bank) / current_liabilities", ["cash", "current_liabilities"],
     ["StatementService.balance_sheet"], "Most conservative liquidity measure — cash-only cover."),
    # ── Working capital ──────────────────────────────────────────────────────────
    ("working_capital", "Working Capital", "working_capital", "$", "higher_better", 0, 0,
     "current_assets - current_liabilities", ["current_assets", "current_liabilities"],
     ["StatementService.balance_sheet"], "Net short-term operating funds available."),
    ("working_capital_ratio", "Working Capital / Assets", "working_capital", "x", "higher_better",
     0, 0, "(current_assets - current_liabilities) / total_assets",
     ["current_assets", "current_liabilities", "total_assets"], ["StatementService.balance_sheet"],
     "Working capital as a share of the asset base."),
    # ── Cash ─────────────────────────────────────────────────────────────────────
    ("cash_balance", "Cash & Bank Balance", "cash", "$", "higher_better", 0, 0,
     "GL cash (1000) + bank (1010)", ["cash"], ["StatementService.balance_sheet"],
     "Total book cash across cash and bank accounts."),
    ("cash_runway_months", "Cash Runway (months)", "cash", "mo", "higher_better", 6, 3,
     "cash / (period_expenses / months_elapsed)", ["cash", "expenses", "months_elapsed"],
     ["StatementService"], "Months of operating expense the current cash can fund."),
    # ── Profitability ────────────────────────────────────────────────────────────
    ("gross_margin_pct", "Gross Margin %", "profitability", "%", "higher_better", 40, 25,
     "(revenue - COGS) / revenue * 100", ["revenue", "cogs"], ["StatementService.profit_and_loss"],
     "Profit after direct cost of goods, before operating expenses."),
    ("operating_margin_pct", "Operating Margin %", "profitability", "%", "higher_better", 15, 5,
     "operating_income / revenue * 100", ["operating_income", "revenue"],
     ["StatementService.profit_and_loss"], "Profitability of core operations (ex-interest)."),
    ("net_profit_margin_pct", "Net Profit Margin %", "profitability", "%", "higher_better", 10, 3,
     "net_income / revenue * 100", ["net_income", "revenue"],
     ["StatementService.profit_and_loss"], "Bottom-line profit per unit of revenue."),
    ("ebitda", "EBITDA", "profitability", "$", "higher_better", 0, 0,
     "operating_income + depreciation", ["operating_income", "depreciation"],
     ["StatementService.profit_and_loss"], "Earnings before interest, tax, depreciation (proxy)."),
    # ── Revenue / Expense / Growth ───────────────────────────────────────────────
    ("gl_total_revenue", "Total Revenue (GL)", "revenue", "$", "higher_better", 0, 0,
     "sum of revenue accounts, YTD", ["revenue"], ["StatementService.profit_and_loss"],
     "Booked GL revenue year-to-date (distinct from the operational sales-pipeline 'revenue' KPI)."),
    ("gl_total_expense", "Total Expense (GL)", "expense", "$", "lower_better", 0, 0,
     "sum of expense accounts, YTD", ["expenses"], ["StatementService.profit_and_loss"],
     "Booked GL expense year-to-date."),
    ("opex_ratio_pct", "Operating Expense Ratio %", "expense", "%", "lower_better", 30, 45,
     "opex / revenue * 100", ["opex", "revenue"], ["StatementService.profit_and_loss"],
     "Operating (SG&A) expense as a share of revenue."),
    ("revenue_growth_pct", "Revenue Growth % (YoY)", "growth", "%", "higher_better", 10, 0,
     "(revenue_ytd - revenue_prior_ytd) / revenue_prior_ytd * 100", ["revenue"],
     ["StatementService.profit_and_loss"], "Year-over-year revenue growth, same period."),
    # ── Efficiency (working-capital cycle) ───────────────────────────────────────
    ("dso_days", "Days Sales Outstanding", "efficiency", "days", "lower_better", 45, 60,
     "AR / revenue * 365", ["ar", "revenue"],
     ["StatementService", "SettlementService"], "Average days to collect receivables."),
    ("dpo_days", "Days Payable Outstanding", "efficiency", "days", "higher_better", 45, 20,
     "AP / COGS * 365", ["ap", "cogs"], ["StatementService"], "Average days taken to pay suppliers."),
    ("dio_days", "Days Inventory Outstanding", "efficiency", "days", "lower_better", 60, 90,
     "inventory / COGS * 365", ["inventory", "cogs"], ["StatementService"],
     "Average days inventory is held before sale."),
    ("cash_conversion_cycle", "Cash Conversion Cycle", "efficiency", "days", "lower_better", 60, 90,
     "DSO + DIO - DPO", ["ar", "inventory", "ap", "revenue", "cogs"], ["StatementService"],
     "Net days cash is tied up in the operating cycle."),
    # ── AR / AP ──────────────────────────────────────────────────────────────────
    ("ar_balance", "Accounts Receivable", "ar_ap", "$", "lower_better", 0, 0,
     "GL AR (1100)", ["ar"], ["StatementService.balance_sheet"], "Outstanding customer receivables."),
    ("ap_balance", "Accounts Payable", "ar_ap", "$", "lower_better", 0, 0,
     "GL AP (2000)", ["ap"], ["StatementService.balance_sheet"], "Outstanding supplier payables."),
    ("ar_overdue_pct", "AR Overdue %", "ar_ap", "%", "lower_better", 10, 25,
     "overdue_AR / total_AR * 100", ["ar_overdue", "ar_total"], ["SettlementService.aging"],
     "Share of receivables past their due bucket."),
    # ── Treasury (F12) ───────────────────────────────────────────────────────────
    ("net_liquidity", "Net Liquidity", "treasury", "$", "higher_better", 0, 0,
     "cash + investments - borrowings", ["net_liquidity"], ["LiquidityService.position"],
     "Treasury net liquidity position."),
    ("total_borrowings", "Total Borrowings", "treasury", "$", "lower_better", 0, 0,
     "sum of active facility outstanding", ["borrowings"], ["LiquidityService.position"],
     "Outstanding treasury borrowings."),
    ("total_investments", "Total Investments", "treasury", "$", "higher_better", 0, 0,
     "sum of active investment outstanding", ["investments"], ["LiquidityService.position"],
     "Outstanding treasury investments."),
    # ── Leverage / Capital structure ─────────────────────────────────────────────
    ("debt_to_equity", "Debt-to-Equity", "leverage", "x", "lower_better", 1, 2,
     "total_liabilities / total_equity", ["total_liabilities", "total_equity"],
     ["StatementService.balance_sheet"], "Financial leverage — creditor vs owner funding."),
    ("debt_ratio", "Debt Ratio", "leverage", "x", "lower_better", 0.5, 0.7,
     "total_liabilities / total_assets", ["total_liabilities", "total_assets"],
     ["StatementService.balance_sheet"], "Share of assets financed by debt."),
    ("equity_ratio", "Equity Ratio", "capital_structure", "x", "higher_better", 0.5, 0.3,
     "total_equity / total_assets", ["total_equity", "total_assets"],
     ["StatementService.balance_sheet"], "Share of assets financed by equity."),
    ("interest_coverage", "Interest Coverage", "leverage", "x", "higher_better", 3, 1.5,
     "operating_income / interest_expense", ["operating_income", "interest_expense"],
     ["StatementService.profit_and_loss"], "How many times operating income covers interest."),
    # ── Returns ──────────────────────────────────────────────────────────────────
    ("return_on_assets_pct", "Return on Assets %", "returns", "%", "higher_better", 5, 2,
     "net_income / total_assets * 100", ["net_income", "total_assets"],
     ["StatementService"], "Profit generated per unit of assets."),
    ("return_on_equity_pct", "Return on Equity %", "returns", "%", "higher_better", 12, 5,
     "net_income / total_equity * 100", ["net_income", "total_equity"],
     ["StatementService"], "Profit generated per unit of owner equity."),
    # ── Budget / Consolidation / FX / Tax ────────────────────────────────────────
    ("budget_variance_pct", "Budget Variance %", "budget", "%", "lower_better", 5, 10,
     "(actual - budget) / budget * 100 (latest locked version)", ["budget", "actual"],
     ["BudgetService.budget_vs_actual"], "Overspend/underspend vs the approved budget."),
    ("company_count", "Group Companies", "consolidation", "#", "higher_better", 0, 0,
     "count of legal entities", ["company_count"], ["CompanyService"],
     "Number of legal entities in the consolidation group."),
    ("intercompany_balance", "Intercompany Net Balance", "consolidation", "$", "lower_better", 0, 0,
     "IC receivable (1900) + IC payable (2900)", ["ic_net"], ["StatementService"],
     "Net intercompany balance — should net to ~0 after elimination."),
    ("fx_net_impact", "Net FX Impact", "fx", "$", "higher_better", 0, 0,
     "FX gain (4930) - FX loss (6960)", ["fx_net"], ["StatementService", "CurrencyService"],
     "Net realized/unrealized foreign-exchange effect in the GL."),
    ("tax_liability", "Tax Liability", "tax", "$", "lower_better", 0, 0,
     "taxes payable (2200) + output tax (2210)", ["tax_liability"], ["StatementService"],
     "Outstanding tax obligation on the balance sheet."),
]


class FinanceKPI:
    __slots__ = ("code", "name", "category", "unit", "direction", "target", "warning",
                 "formula", "inputs", "dependencies", "explanation")

    def __init__(self, row):
        (self.code, self.name, self.category, self.unit, self.direction, self.target,
         self.warning, self.formula, self.inputs, self.dependencies, self.explanation) = row

    @property
    def native_key(self):
        return f"finance_{self.code}"

    def descriptor(self) -> dict:
        """The full AI-readiness descriptor for one KPI."""
        return {
            "code": self.code, "name": self.name, "category": self.category, "unit": self.unit,
            "direction": self.direction, "target": self.target, "warning_threshold": self.warning,
            "formula": self.formula, "inputs": list(self.inputs),
            "dependencies": list(self.dependencies), "explanation": self.explanation,
            "source_type": "native", "native_key": self.native_key, "owner": "financial_kpis",
        }


CATALOG = [FinanceKPI(row) for row in _CATALOG]
BY_CODE = {k.code: k for k in CATALOG}
CATEGORIES = sorted({k.category for k in CATALOG})
