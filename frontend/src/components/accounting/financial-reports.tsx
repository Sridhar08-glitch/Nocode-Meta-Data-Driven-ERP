"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBalanceSheet,
  useGeneralLedger,
  useLedgerAccounts,
  useProfitLoss,
  useTrialBalance,
} from "@/lib/ledger/hooks";

type ReportKind = "trial_balance" | "profit_loss" | "balance_sheet" | "general_ledger";
const REPORTS: { value: ReportKind; label: string }[] = [
  { value: "trial_balance", label: "Trial Balance" },
  { value: "profit_loss", label: "Profit & Loss" },
  { value: "balance_sheet", label: "Balance Sheet" },
  { value: "general_ledger", label: "General Ledger" },
];

function Amount({ value }: { value: string }) {
  return <span className="font-mono tabular-nums">{value}</span>;
}

/** Financial reports (Phase P2.3) — trial balance, P&L, balance sheet, general ledger. */
export function FinancialReports() {
  const [kind, setKind] = useState<ReportKind>("trial_balance");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="text-xs text-muted-foreground">Report</label>
          <Select value={kind} onValueChange={(v) => setKind(v as ReportKind)}>
            <SelectTrigger aria-label="Report" className="w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              {REPORTS.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {(kind === "profit_loss" || kind === "general_ledger") && (
          <div>
            <label className="text-xs text-muted-foreground" htmlFor="rep-from">From</label>
            <Input id="rep-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
          </div>
        )}
        <div>
          <label className="text-xs text-muted-foreground" htmlFor="rep-to">
            {kind === "balance_sheet" || kind === "trial_balance" ? "As of" : "To"}
          </label>
          <Input id="rep-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        </div>
      </div>

      {kind === "trial_balance" && <TrialBalanceReport asOf={to || undefined} />}
      {kind === "profit_loss" && <ProfitLossReport from={from || undefined} to={to || undefined} />}
      {kind === "balance_sheet" && <BalanceSheetReport asOf={to || undefined} />}
      {kind === "general_ledger" && <GeneralLedgerReport from={from || undefined} to={to || undefined} />}
    </div>
  );
}

function TrialBalanceReport({ asOf }: { asOf?: string }) {
  const q = useTrialBalance(asOf);
  if (q.isLoading) return <Skeleton className="h-48 w-full" />;
  const d = q.data;
  if (!d) return null;
  return (
    <div className="space-y-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th className="py-1 text-left">Code</th><th className="text-left">Account</th>
            <th className="text-right">Debit</th><th className="text-right">Credit</th>
          </tr>
        </thead>
        <tbody>
          {d.rows.map((r) => (
            <tr key={r.account_id} className="border-b last:border-0">
              <td className="py-1 font-mono text-muted-foreground">{r.code}</td>
              <td>{r.name}</td>
              <td className="text-right"><Amount value={r.debit} /></td>
              <td className="text-right"><Amount value={r.credit} /></td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t font-medium">
            <td colSpan={2} className="py-1">Total</td>
            <td className="text-right"><Amount value={d.total_debit} /></td>
            <td className="text-right"><Amount value={d.total_credit} /></td>
          </tr>
        </tfoot>
      </table>
      <Badge variant={d.balanced ? "default" : "destructive"}>{d.balanced ? "Balanced" : "Out of balance"}</Badge>
    </div>
  );
}

function ProfitLossReport({ from, to }: { from?: string; to?: string }) {
  const q = useProfitLoss(from, to);
  if (q.isLoading) return <Skeleton className="h-48 w-full" />;
  const d = q.data;
  if (!d) return null;
  return (
    <div className="space-y-3 text-sm">
      <Section title="Revenue" rows={d.revenue} total={d.total_revenue} />
      <Section title="Expenses" rows={d.expense} total={d.total_expense} />
      <div className="flex justify-between border-t pt-2 font-semibold">
        <span>Net income</span><Amount value={d.net_income} />
      </div>
    </div>
  );
}

function BalanceSheetReport({ asOf }: { asOf?: string }) {
  const q = useBalanceSheet(asOf);
  if (q.isLoading) return <Skeleton className="h-48 w-full" />;
  const d = q.data;
  if (!d) return null;
  return (
    <div className="space-y-3 text-sm">
      <Section title="Assets" rows={d.assets} total={d.total_assets} />
      <Section title="Liabilities" rows={d.liabilities} total={d.total_liabilities} />
      <Section title="Equity" rows={d.equity} total={d.total_equity} />
      <div className="flex justify-between border-t pt-2 font-semibold">
        <span>Liabilities + Equity</span><Amount value={d.total_liabilities_equity} />
      </div>
      <Badge variant={d.balanced ? "default" : "destructive"}>
        {d.balanced ? "Balanced (A = L + E)" : "Out of balance"}
      </Badge>
    </div>
  );
}

function Section({ title, rows, total }: { title: string; rows: { code: string; name: string; amount: string }[]; total: string }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="mt-1 space-y-0.5">
        {rows.map((r, i) => (
          <li key={`${r.code}-${i}`} className="flex justify-between">
            <span><span className="font-mono text-muted-foreground">{r.code}</span> {r.name}</span>
            <Amount value={r.amount} />
          </li>
        ))}
        {rows.length === 0 && <li className="text-muted-foreground">None</li>}
      </ul>
      <div className="mt-1 flex justify-between border-t pt-1 font-medium">
        <span>Total {title.toLowerCase()}</span><Amount value={total} />
      </div>
    </div>
  );
}

function GeneralLedgerReport({ from, to }: { from?: string; to?: string }) {
  const accounts = useLedgerAccounts();
  const [accountId, setAccountId] = useState<string | null>(null);
  const q = useGeneralLedger(accountId, from, to);
  const postable = (accounts.data ?? []).filter((a) => !a.is_group);

  return (
    <div className="space-y-3">
      <Select value={accountId ?? ""} onValueChange={setAccountId}>
        <SelectTrigger aria-label="Account" className="w-72"><SelectValue placeholder="Select an account" /></SelectTrigger>
        <SelectContent>
          {postable.map((a) => <SelectItem key={a.id} value={a.id}>{a.code} — {a.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {!accountId ? (
        <p className="text-sm text-muted-foreground">Choose an account to view its activity.</p>
      ) : q.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : q.data?.account ? (
        <div className="space-y-1 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>Opening balance</span><Amount value={q.data.opening_balance} />
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-1 text-left">Date</th><th className="text-left">Entry</th>
                <th className="text-right">Debit</th><th className="text-right">Credit</th><th className="text-right">Balance</th>
              </tr>
            </thead>
            <tbody>
              {q.data.lines.map((l, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1">{l.date}</td>
                  <td className="font-mono text-xs">{l.entry_number}</td>
                  <td className="text-right"><Amount value={l.debit} /></td>
                  <td className="text-right"><Amount value={l.credit} /></td>
                  <td className="text-right"><Amount value={l.balance} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex justify-between border-t pt-1 font-medium">
            <span>Closing balance</span><Amount value={q.data.closing_balance} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
