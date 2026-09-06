/**
 * General Ledger client (Phase P2.2) — chart of accounts, fiscal periods, journal entries, and
 * posting rules over `/api/v1/ledger/` (backend P2.2). The posting bus enforces the double-entry
 * invariant + period locks server-side; this client never recomputes the books, it only submits
 * balanced lines and renders results. Posted entries are immutable (reverse, never edit).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";
export type EntryStatus = "draft" | "posted" | "reversed";
export type PeriodStatus = "open" | "closed" | "locked";

export interface LedgerAccount {
  id: string;
  code: string;
  name: string;
  account_type: AccountType;
  parent: string | null;
  is_group: boolean;
  is_active: boolean;
  currency: string;
  description: string;
  normal_balance: "debit" | "credit";
  created_at: string;
  updated_at: string;
}
export interface AccountingPeriod {
  id: string;
  code: string;
  name: string;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  fiscal_year: string;
  closed_at: string | null;
  closed_by: string | null;
}
export interface JournalLine {
  id?: string;
  account: string;
  account_code?: string;
  account_name?: string;
  line_no?: number;
  debit: string | number;
  credit: string | number;
  memo?: string;
  partner_ref?: string;
}
export interface JournalEntry {
  id: string;
  entry_number: string;
  date: string;
  period: string | null;
  memo: string;
  currency: string;
  status: EntryStatus;
  source_module: string;
  source_ref: string;
  posting_rule_key: string;
  posted_at: string | null;
  reverses: string | null;
  lines: JournalLine[];
  created_at: string;
}
export interface PostingRule {
  id: string;
  event_type: string;
  name: string;
  template: Array<Record<string, unknown>>;
  is_active: boolean;
}

export interface JournalEntryWrite {
  date: string;
  memo?: string;
  currency?: string;
  source_module?: string;
  source_ref?: string;
  post?: boolean;
  lines: Array<{ account_code?: string; account_id?: string; debit?: string | number; credit?: string | number; memo?: string }>;
}

const L = "/api/v1/ledger";

export const ledgerApi = {
  // accounts
  listAccounts: (type?: AccountType) => apiGet<LedgerAccount[]>(`${L}/accounts/${type ? `?type=${type}` : ""}`),
  createAccount: (data: Partial<LedgerAccount>) => apiSend<LedgerAccount>(`${L}/accounts/`, "POST", data),
  updateAccount: (id: string, data: Partial<LedgerAccount>) => apiSend<LedgerAccount>(`${L}/accounts/${id}/`, "PATCH", data),
  deleteAccount: (id: string) => apiSend<void>(`${L}/accounts/${id}/`, "DELETE"),
  // periods
  listPeriods: () => apiGet<AccountingPeriod[]>(`${L}/periods/`),
  createPeriod: (data: Partial<AccountingPeriod>) => apiSend<AccountingPeriod>(`${L}/periods/`, "POST", data),
  closePeriod: (id: string, lock = false) => apiSend<AccountingPeriod>(`${L}/periods/${id}/close/`, "POST", { lock }),
  reopenPeriod: (id: string) => apiSend<AccountingPeriod>(`${L}/periods/${id}/reopen/`, "POST", {}),
  // journal entries
  listEntries: (params?: { status?: EntryStatus; source_module?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.source_module) q.set("source_module", params.source_module);
    const qs = q.toString();
    return apiGet<JournalEntry[]>(`${L}/entries/${qs ? `?${qs}` : ""}`);
  },
  getEntry: (id: string) => apiGet<JournalEntry>(`${L}/entries/${id}/`),
  createEntry: (data: JournalEntryWrite) => apiSend<JournalEntry>(`${L}/entries/`, "POST", data),
  postEntry: (id: string) => apiSend<JournalEntry>(`${L}/entries/${id}/post/`, "POST", {}),
  reverseEntry: (id: string) => apiSend<JournalEntry>(`${L}/entries/${id}/reverse/`, "POST", {}),
  deleteEntry: (id: string) => apiSend<void>(`${L}/entries/${id}/`, "DELETE"),
  // posting rules
  listRules: () => apiGet<PostingRule[]>(`${L}/posting-rules/`),
  // setup (P2.3)
  seedChart: () => apiSend<{ created: number; skipped: number }>(`${L}/seed-chart/`, "POST", {}),
  generateFiscalYear: (year: number, start_month = 1) =>
    apiSend<{ created: number; skipped: number; fiscal_year: string }>(`${L}/fiscal-years/`, "POST", { year, start_month }),
  // financial reports (P2.3)
  trialBalance: (asOf?: string) =>
    apiGet<TrialBalance>(`${L}/reports/trial-balance/${asOf ? `?as_of=${asOf}` : ""}`),
  profitLoss: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("date_from", from);
    if (to) q.set("date_to", to);
    const qs = q.toString();
    return apiGet<ProfitLoss>(`${L}/reports/profit-loss/${qs ? `?${qs}` : ""}`);
  },
  balanceSheet: (asOf?: string) =>
    apiGet<BalanceSheet>(`${L}/reports/balance-sheet/${asOf ? `?as_of=${asOf}` : ""}`),
  generalLedger: (accountId: string, from?: string, to?: string) => {
    const q = new URLSearchParams({ account: accountId });
    if (from) q.set("date_from", from);
    if (to) q.set("date_to", to);
    return apiGet<GeneralLedger>(`${L}/reports/general-ledger/?${q.toString()}`);
  },
};

export interface TrialBalanceRow {
  account_id: string; code: string; name: string; account_type: AccountType; debit: string; credit: string;
}
export interface TrialBalance {
  as_of: string | null; rows: TrialBalanceRow[]; total_debit: string; total_credit: string; balanced: boolean;
}
export interface AmountRow { code: string; name: string; amount: string }
export interface ProfitLoss {
  date_from: string | null; date_to: string | null;
  revenue: AmountRow[]; expense: AmountRow[];
  total_revenue: string; total_expense: string; net_income: string;
}
export interface BalanceSheet {
  as_of: string | null;
  assets: AmountRow[]; liabilities: AmountRow[]; equity: AmountRow[];
  total_assets: string; total_liabilities: string; total_equity: string;
  total_liabilities_equity: string; balanced: boolean;
}
export interface GeneralLedgerLine {
  date: string; entry_number: string; memo: string; debit: string; credit: string; balance: string;
}
export interface GeneralLedger {
  account: { id: string; code: string; name: string; account_type: AccountType } | null;
  opening_balance: string; lines: GeneralLedgerLine[]; closing_balance: string;
}
