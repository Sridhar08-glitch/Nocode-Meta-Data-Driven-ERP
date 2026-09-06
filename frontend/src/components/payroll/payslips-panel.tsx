"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { usePayslip, usePayslips } from "@/lib/payroll/hooks";

/** Payslips (Phase P2.8) — read-only list, filterable by run, with a line-level breakdown
 * (earnings / deductions / net). Payslips are immutable once posted. */
export function PayslipsPanel() {
  const [runFilter, setRunFilter] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const payslips = usePayslips(runFilter.trim() ? { payroll_run_id: runFilter.trim() } : undefined);

  const rows = payslips.data ?? [];

  return (
    <div className="space-y-3">
      <div className="max-w-md">
        <Label htmlFor="ps-run">Filter by run id</Label>
        <Input
          id="ps-run"
          value={runFilter}
          onChange={(e) => setRunFilter(e.target.value)}
          placeholder="Payroll run UUID (optional)"
        />
      </div>

      {payslips.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : payslips.isError ? (
        <ErrorState title="Couldn't load payslips" />
      ) : rows.length === 0 ? (
        <EmptyState title="No payslips" description="Calculate a payroll run to generate payslips." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Employee</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Gross</th>
                <th className="px-3 py-2 text-right">Deductions</th>
                <th className="px-3 py-2 text-right">Net</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{p.employee_record_id?.slice(0, 8)}</td>
                  <td className="px-3 py-2"><Badge variant="secondary">{p.status}</Badge></td>
                  <td className="px-3 py-2 text-right font-mono">{p.total_gross}</td>
                  <td className="px-3 py-2 text-right font-mono">{p.total_deductions}</td>
                  <td className="px-3 py-2 text-right font-mono">{p.total_net}</td>
                  <td className="px-3 py-2 text-right">
                    <Button variant="ghost" size="sm" onClick={() => setOpenId(p.id)}>View</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {openId && <PayslipDialog payslipId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}

function PayslipDialog({ payslipId, onClose }: { payslipId: string; onClose: () => void }) {
  const payslip = usePayslip(payslipId);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Payslip</DialogTitle>
        </DialogHeader>
        {payslip.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : payslip.isError || !payslip.data ? (
          <ErrorState title="Couldn't load payslip" />
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3 text-sm">
              <Stat label="Gross" value={payslip.data.total_gross} />
              <Stat label="Deductions" value={payslip.data.total_deductions} />
              <Stat label="Net" value={payslip.data.total_net} />
            </div>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">Code</th>
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {(payslip.data.lines ?? []).map((l, i) => (
                    <tr key={`${l.code}-${i}`} className="border-b last:border-0">
                      <td className="px-3 py-2 font-mono">{l.code}</td>
                      <td className="px-3 py-2">{l.name}</td>
                      <td className="px-3 py-2">
                        <Badge variant={l.component_type === "deduction" ? "destructive" : "secondary"}>
                          {l.component_type}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{l.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="font-mono text-lg font-medium">{value}</p>
    </div>
  );
}
