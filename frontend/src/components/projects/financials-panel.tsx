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
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { CostEntry, CostSource, ProjectFinancials } from "@/lib/projects/api";
import {
  useCostEntries,
  usePostCost,
  useProjectFinancials,
  useRollupProject,
} from "@/lib/projects/hooks";
import { useTenant } from "@/lib/tenant/context";

const SOURCES: { value: CostSource; label: string }[] = [
  { value: "payroll", label: "Payroll" },
  { value: "procurement", label: "Procurement" },
  { value: "asset", label: "Asset" },
  { value: "expense", label: "Expense" },
  { value: "timesheet", label: "Timesheet" },
  { value: "other", label: "Other" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/** Native financials / EVM panel (Phase P2.10) — enter a project record id, then view budget,
 * profitability, and earned-value metrics, post cost entries, and roll them up onto the project.
 * All financial math runs server-side. */
export function FinancialsPanel() {
  const canManage = useCanManage();
  const [projectId, setProjectId] = useState("");
  const [active, setActive] = useState<string | null>(null);

  function load() {
    const id = projectId.trim();
    setActive(id || null);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border p-4">
        <label className="flex-1 space-y-1">
          <span className="text-xs font-medium">Project record id</span>
          <Input
            aria-label="Project record id"
            placeholder="project record id (raw UUID — no picker yet)"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          />
        </label>
        <Button onClick={load} disabled={!projectId.trim()}>
          Load
        </Button>
      </div>

      {!active ? (
        <EmptyState title="Enter a project record id" description="Load a project to see its financials, cost entries, and earned value." />
      ) : (
        <>
          <FinancialsCards projectRecordId={active} />
          <CostEntries projectRecordId={active} canManage={canManage} />
        </>
      )}
    </div>
  );
}

export function FinancialsCards({ projectRecordId }: { projectRecordId: string }) {
  const fin = useProjectFinancials(projectRecordId);

  if (fin.isLoading) return <Skeleton className="h-40 w-full" />;
  if (fin.isError) return <ErrorState title="Couldn't load financials" />;
  if (!fin.data) return null;

  const d: ProjectFinancials = fin.data;

  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Budget</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Planned budget" value={d.budget.planned_budget} />
          <Metric label="Actual cost" value={d.budget.actual_cost} />
          <Metric label="Remaining" value={d.budget.remaining_budget} />
          <Metric
            label="Budget variance"
            value={d.budget.budget_variance}
            badge={
              <Badge variant={d.budget.over_budget ? "destructive" : "secondary"}>
                {d.budget.over_budget ? "Over budget" : `${d.budget.utilization_percent}% used`}
              </Badge>
            }
          />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Profitability</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Revenue" value={d.profitability.revenue} />
          <Metric label="Cost" value={d.profitability.cost} />
          <Metric label="Profit" value={d.profitability.profit} />
          <Metric label="Margin" value={`${d.profitability.margin_percent}%`} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Earned value (EVM)</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="CPI" value={String(d.earned_value.cpi)} />
          <Metric label="SPI" value={String(d.earned_value.spi)} />
          <Metric label="Cost variance" value={d.earned_value.cost_variance} />
          <Metric label="Schedule variance" value={d.earned_value.schedule_variance} />
          <Metric label="Estimate at completion" value={d.earned_value.estimate_at_completion} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Progress</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Metric label="Progress" value={`${d.progress_percent}%`} />
          <Metric label="Tasks" value={String(d.task_count)} />
          <Metric label="Completed tasks" value={String(d.completed_tasks)} />
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, badge }: { label: string; value: string; badge?: React.ReactNode }) {
  return (
    <div className="space-y-1 rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-lg font-semibold">{value}</p>
      {badge}
    </div>
  );
}

export function CostEntries({ projectRecordId, canManage }: { projectRecordId: string; canManage: boolean }) {
  const entries = useCostEntries(projectRecordId);
  const rollup = useRollupProject();
  const rows = entries.data ?? [];

  async function doRollup() {
    try {
      const res = await rollup.mutateAsync(projectRecordId);
      toast.success(`Rolled up — total cost ${res.total_cost}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rollup failed");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium">Cost entries</h2>
        <Button variant="outline" onClick={doRollup} disabled={rollup.isPending}>
          {rollup.isPending ? "Rolling up…" : "Roll up"}
        </Button>
      </div>

      {canManage && <PostCostForm projectRecordId={projectRecordId} />}

      {entries.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : entries.isError ? (
        <ErrorState title="Couldn't load cost entries" />
      ) : rows.length === 0 ? (
        <EmptyState title="No cost entries" description="Post a cost entry above, then roll it up onto the project." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Description</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c: CostEntry) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{c.entry_date}</td>
                  <td className="px-3 py-2">
                    <Badge variant="secondary">{SOURCES.find((s) => s.value === c.source)?.label ?? c.source}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{c.amount}</td>
                  <td className="px-3 py-2">{c.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function PostCostForm({ projectRecordId }: { projectRecordId: string }) {
  const post = usePostCost();
  const [source, setSource] = useState<CostSource>("other");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [entryDate, setEntryDate] = useState(todayIso());

  async function save() {
    if (!amount.trim()) {
      toast.error("An amount is required");
      return;
    }
    try {
      await post.mutateAsync({
        project_record_id: projectRecordId,
        source,
        amount: amount.trim(),
        description: description.trim(),
        entry_date: entryDate,
      });
      toast.success("Cost entry posted");
      setAmount("");
      setDescription("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not post cost");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border p-4">
      <div className="w-44">
        <Label htmlFor="cost-source">Source</Label>
        <Select value={source} onValueChange={(v) => setSource(v as CostSource)}>
          <SelectTrigger id="cost-source" aria-label="Cost source">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SOURCES.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-40">
        <Label htmlFor="cost-amount">Amount</Label>
        <Input id="cost-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="1000" />
      </div>
      <div className="flex-1">
        <Label htmlFor="cost-desc">Description</Label>
        <Input id="cost-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Subcontractor invoice" />
      </div>
      <div className="w-44">
        <Label htmlFor="cost-date">Entry date</Label>
        <Input id="cost-date" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
      </div>
      <Button onClick={save} disabled={post.isPending}>
        {post.isPending ? "Posting…" : "Post cost"}
      </Button>
    </div>
  );
}
