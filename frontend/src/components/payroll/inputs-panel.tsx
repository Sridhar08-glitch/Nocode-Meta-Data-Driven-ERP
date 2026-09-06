"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { AdjustmentType } from "@/lib/payroll/api";
import {
  useAdjustments,
  useAdvances,
  useApproveOvertime,
  useCreateAdjustment,
  useCreateAdvance,
  useCreateLoan,
  useCreateOvertime,
  useLoans,
  useOvertime,
} from "@/lib/payroll/hooks";

type Tab = "loans" | "advances" | "overtime" | "adjustments";
const TABS: { value: Tab; label: string }[] = [
  { value: "loans", label: "Loans" },
  { value: "advances", label: "Advances" },
  { value: "overtime", label: "Overtime" },
  { value: "adjustments", label: "Adjustments" },
];

/** Payroll inputs (Phase P2.8) — loans & advances (with running balance), overtime (create +
 * approve), and one-time adjustments. These feed the next payroll calculation server-side. */
export function InputsPanel() {
  const [tab, setTab] = useState<Tab>("loans");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1" role="tablist" aria-label="Input type">
        {TABS.map((t) => (
          <Button
            key={t.value}
            role="tab"
            aria-selected={tab === t.value}
            variant={tab === t.value ? "default" : "outline"}
            size="sm"
            onClick={() => setTab(t.value)}
          >
            {t.label}
          </Button>
        ))}
      </div>
      {tab === "loans" && <LoansTab />}
      {tab === "advances" && <AdvancesTab />}
      {tab === "overtime" && <OvertimeTab />}
      {tab === "adjustments" && <AdjustmentsTab />}
    </div>
  );
}

function EmployeeField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex-1">
      <Label htmlFor="emp-id">Employee record id</Label>
      <Input id="emp-id" value={value} onChange={(e) => onChange(e.target.value)} placeholder="Employee UUID" />
    </div>
  );
}

// ── Loans ──────────────────────────────────────────────────────────────────
function LoansTab() {
  const loans = useLoans();
  const create = useCreateLoan();
  const [employee, setEmployee] = useState("");
  const [amount, setAmount] = useState("");
  const [installment, setInstallment] = useState("");
  const [reference, setReference] = useState("");

  async function submit() {
    if (!employee.trim() || !amount.trim()) {
      toast.error("Employee and amount are required");
      return;
    }
    try {
      await create.mutateAsync({
        employee_record_id: employee.trim(),
        amount: amount.trim(),
        installment: installment.trim() || "0",
        reference: reference.trim(),
      });
      toast.success("Loan created");
      setAmount("");
      setInstallment("");
      setReference("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create loan");
    }
  }

  return (
    <div className="space-y-4">
      <div className="max-w-2xl space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap gap-3">
          <EmployeeField value={employee} onChange={setEmployee} />
          <div className="w-32">
            <Label htmlFor="loan-amt">Amount</Label>
            <Input id="loan-amt" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-32">
            <Label htmlFor="loan-inst">Installment</Label>
            <Input id="loan-inst" value={installment} onChange={(e) => setInstallment(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-40">
            <Label htmlFor="loan-ref">Reference</Label>
            <Input id="loan-ref" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end">
          <Button onClick={submit} disabled={create.isPending}>{create.isPending ? "Saving…" : "Create loan"}</Button>
        </div>
      </div>
      <BalanceTable
        loading={loans.isLoading}
        rows={(loans.data ?? []).map((l) => ({ id: l.id, employee: l.employee_record_id, amount: l.amount, balance: l.balance, status: l.status }))}
        emptyTitle="No loans"
      />
    </div>
  );
}

// ── Advances ───────────────────────────────────────────────────────────────
function AdvancesTab() {
  const advances = useAdvances();
  const create = useCreateAdvance();
  const [employee, setEmployee] = useState("");
  const [amount, setAmount] = useState("");
  const [installment, setInstallment] = useState("");
  const [reference, setReference] = useState("");

  async function submit() {
    if (!employee.trim() || !amount.trim()) {
      toast.error("Employee and amount are required");
      return;
    }
    try {
      await create.mutateAsync({
        employee_record_id: employee.trim(),
        amount: amount.trim(),
        installment: installment.trim() || "0",
        reference: reference.trim(),
      });
      toast.success("Advance created");
      setAmount("");
      setInstallment("");
      setReference("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create advance");
    }
  }

  return (
    <div className="space-y-4">
      <div className="max-w-2xl space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap gap-3">
          <EmployeeField value={employee} onChange={setEmployee} />
          <div className="w-32">
            <Label htmlFor="adv-amt">Amount</Label>
            <Input id="adv-amt" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-32">
            <Label htmlFor="adv-inst">Installment</Label>
            <Input id="adv-inst" value={installment} onChange={(e) => setInstallment(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-40">
            <Label htmlFor="adv-ref">Reference</Label>
            <Input id="adv-ref" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end">
          <Button onClick={submit} disabled={create.isPending}>{create.isPending ? "Saving…" : "Create advance"}</Button>
        </div>
      </div>
      <BalanceTable
        loading={advances.isLoading}
        rows={(advances.data ?? []).map((a) => ({ id: a.id, employee: a.employee_record_id, amount: a.amount, balance: a.balance, status: a.status }))}
        emptyTitle="No advances"
      />
    </div>
  );
}

// ── Overtime ───────────────────────────────────────────────────────────────
function OvertimeTab() {
  const overtime = useOvertime();
  const create = useCreateOvertime();
  const approve = useApproveOvertime();
  const [employee, setEmployee] = useState("");
  const [hours, setHours] = useState("");
  const [rate, setRate] = useState("");
  const [multiplier, setMultiplier] = useState("1.5");

  async function submit() {
    if (!employee.trim() || !hours.trim()) {
      toast.error("Employee and hours are required");
      return;
    }
    try {
      await create.mutateAsync({
        employee_record_id: employee.trim(),
        hours: hours.trim(),
        rate: rate.trim() || "0",
        multiplier: multiplier.trim() || "1.5",
      });
      toast.success("Overtime logged");
      setHours("");
      setRate("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not log overtime");
    }
  }

  async function doApprove(id: string) {
    try {
      await approve.mutateAsync(id);
      toast.success("Overtime approved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not approve");
    }
  }

  const rows = overtime.data ?? [];

  return (
    <div className="space-y-4">
      <div className="max-w-2xl space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap gap-3">
          <EmployeeField value={employee} onChange={setEmployee} />
          <div className="w-24">
            <Label htmlFor="ot-hours">Hours</Label>
            <Input id="ot-hours" value={hours} onChange={(e) => setHours(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-24">
            <Label htmlFor="ot-rate">Rate</Label>
            <Input id="ot-rate" value={rate} onChange={(e) => setRate(e.target.value)} inputMode="decimal" />
          </div>
          <div className="w-28">
            <Label htmlFor="ot-mult">Multiplier</Label>
            <Input id="ot-mult" value={multiplier} onChange={(e) => setMultiplier(e.target.value)} inputMode="decimal" />
          </div>
        </div>
        <div className="flex justify-end">
          <Button onClick={submit} disabled={create.isPending}>{create.isPending ? "Saving…" : "Log overtime"}</Button>
        </div>
      </div>
      {overtime.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState title="No overtime" />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Employee</th>
                <th className="px-3 py-2 text-right">Hours</th>
                <th className="px-3 py-2 text-right">Rate</th>
                <th className="px-3 py-2 text-right">×</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{o.employee_record_id?.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-right font-mono">{o.hours}</td>
                  <td className="px-3 py-2 text-right font-mono">{o.rate}</td>
                  <td className="px-3 py-2 text-right font-mono">{o.multiplier}</td>
                  <td className="px-3 py-2"><Badge variant="secondary">{o.status}</Badge></td>
                  <td className="px-3 py-2 text-right">
                    {o.status !== "approved" && (
                      <Button variant="outline" size="sm" disabled={approve.isPending} onClick={() => doApprove(o.id)}>
                        Approve
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Adjustments ────────────────────────────────────────────────────────────
const ADJ_TYPES: { value: AdjustmentType; label: string }[] = [
  { value: "bonus", label: "Bonus" },
  { value: "correction", label: "Correction" },
  { value: "one_time", label: "One-time" },
  { value: "deduction", label: "Deduction" },
  { value: "recovery", label: "Recovery" },
];

function AdjustmentsTab() {
  const adjustments = useAdjustments();
  const create = useCreateAdjustment();
  const [employee, setEmployee] = useState("");
  const [type, setType] = useState<AdjustmentType>("bonus");
  const [amount, setAmount] = useState("");
  const [name, setName] = useState("");

  async function submit() {
    if (!employee.trim() || !amount.trim()) {
      toast.error("Employee and amount are required");
      return;
    }
    try {
      await create.mutateAsync({
        employee_record_id: employee.trim(),
        adj_type: type,
        amount: amount.trim(),
        name: name.trim(),
      });
      toast.success("Adjustment created");
      setAmount("");
      setName("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create adjustment");
    }
  }

  const rows = adjustments.data ?? [];

  return (
    <div className="space-y-4">
      <div className="max-w-2xl space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap gap-3">
          <EmployeeField value={employee} onChange={setEmployee} />
          <div className="w-36">
            <Label htmlFor="adj-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as AdjustmentType)}>
              <SelectTrigger id="adj-type" aria-label="Adjustment type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ADJ_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="w-32">
            <Label htmlFor="adj-amt">Amount</Label>
            <Input id="adj-amt" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </div>
        </div>
        <div>
          <Label htmlFor="adj-name">Name / memo</Label>
          <Input id="adj-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q1 performance bonus" />
        </div>
        <div className="flex justify-end">
          <Button onClick={submit} disabled={create.isPending}>{create.isPending ? "Saving…" : "Create adjustment"}</Button>
        </div>
      </div>
      {adjustments.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState title="No adjustments" />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Employee</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{a.employee_record_id?.slice(0, 8)}</td>
                  <td className="px-3 py-2">{a.adj_type}</td>
                  <td className="px-3 py-2">{a.name}</td>
                  <td className="px-3 py-2 text-right font-mono">{a.amount}</td>
                  <td className="px-3 py-2"><Badge variant="secondary">{a.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── shared balance table (loans/advances) ───────────────────────────────────
function BalanceTable({
  loading,
  rows,
  emptyTitle,
}: {
  loading: boolean;
  rows: { id: string; employee: string; amount: string; balance: string; status: string }[];
  emptyTitle: string;
}) {
  if (loading) return <Skeleton className="h-24 w-full" />;
  if (rows.length === 0) return <EmptyState title={emptyTitle} />;
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-3 py-2">Employee</th>
            <th className="px-3 py-2 text-right">Amount</th>
            <th className="px-3 py-2 text-right">Balance</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b last:border-0">
              <td className="px-3 py-2 font-mono text-xs">{r.employee?.slice(0, 8)}</td>
              <td className="px-3 py-2 text-right font-mono">{r.amount}</td>
              <td className="px-3 py-2 text-right font-mono">{r.balance}</td>
              <td className="px-3 py-2"><Badge variant="secondary">{r.status}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
