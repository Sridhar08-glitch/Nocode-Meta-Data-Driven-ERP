"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { RunStatus } from "@/lib/payroll/api";
import {
  useApproveRun,
  useCalculateRun,
  useCanManagePayroll,
  useLockRun,
  usePostRun,
  useRun,
  useRunRegister,
  useRunSummary,
} from "@/lib/payroll/hooks";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  draft: "secondary",
  processing: "default",
  completed: "default",
  approved: "success",
  posted: "success",
  cancelled: "destructive",
  locked: "destructive",
};

/**
 * Payroll run lifecycle (Phase P2.8) — surfaces the server-driven state machine
 * draft → (calculate) → completed → (approve) → approved → (post) → posted → (lock) → locked.
 * Each action is enabled only from the valid prior state. Segregation of duties (creator can't
 * approve, approver can't post) is enforced server-side; the 400 message is surfaced via toast.
 */
export function RunLifecycle({ runId }: { runId: string }) {
  const run = useRun(runId);
  const summary = useRunSummary(runId);
  const register = useRunRegister(runId);
  const canManage = useCanManagePayroll();

  const calculate = useCalculateRun();
  const approve = useApproveRun();
  const post = usePostRun();
  const lock = useLockRun();

  if (run.isLoading) return <Skeleton className="h-64 w-full" />;
  if (run.isError || !run.data) return <ErrorState title="Couldn't load run" />;

  const r = run.data;
  const status = r.status as RunStatus;
  const pending = calculate.isPending || approve.isPending || post.isPending || lock.isPending;

  async function act(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  const registerRows = register.data?.rows ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
        <div className="flex items-center gap-2">
          <span className="font-medium">Run status</span>
          <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
          {r.journal_entry_id && (
            <span className="text-xs text-muted-foreground">JE {r.journal_entry_id.slice(0, 8)}</span>
          )}
        </div>
        {canManage && (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={pending || status !== "draft"}
              onClick={() => act("Run calculated", () => calculate.mutateAsync(runId))}
            >
              Calculate
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || status !== "completed"}
              onClick={() => act("Run approved", () => approve.mutateAsync(runId))}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || status !== "approved"}
              onClick={() => act("Run posted", () => post.mutateAsync(runId))}
            >
              Post
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || status !== "posted"}
              onClick={() => act("Run locked", () => lock.mutateAsync(runId))}
            >
              Lock
            </Button>
          </div>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Employees" value={String(summary.data?.employee_count ?? r.employee_count)} />
        <Stat label="Gross" value={summary.data?.total_gross ?? r.total_gross} />
        <Stat label="Deductions" value={summary.data?.total_deductions ?? r.total_deductions} />
        <Stat label="Net" value={summary.data?.total_net ?? r.total_net} />
      </dl>

      <div>
        <h3 className="mb-2 text-sm font-medium">Payslip register</h3>
        {register.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : registerRows.length === 0 ? (
          <p className="rounded-md border p-4 text-sm text-muted-foreground">
            No payslips yet — calculate the run to generate them.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Employee</th>
                  <th className="px-3 py-2 text-right">Gross</th>
                  <th className="px-3 py-2 text-right">Deductions</th>
                  <th className="px-3 py-2 text-right">Net</th>
                </tr>
              </thead>
              <tbody>
                {registerRows.map((row, i) => (
                  <tr key={row.payslip_id ?? i} className="border-b last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{row.employee_record_id?.slice(0, 8)}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.total_gross}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.total_deductions}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.total_net}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-mono text-lg font-medium">{value}</dd>
    </div>
  );
}
