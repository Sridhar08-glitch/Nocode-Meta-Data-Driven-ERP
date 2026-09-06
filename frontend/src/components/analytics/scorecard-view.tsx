"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { ScorecardRole, ScorecardSummary } from "@/lib/analytics/api";
import {
  useCanManageAnalytics,
  useCheckAlerts,
  useEnsureSetup,
  useScorecard,
  useSnapshot,
} from "@/lib/analytics/hooks";
import { ApiError } from "@/lib/api/errors";

import { KpiCard } from "./kpi-card";

export const SCORECARD_ROLES: { value: ScorecardRole; label: string }[] = [
  { value: "ceo", label: "CEO" },
  { value: "cfo", label: "CFO" },
  { value: "coo", label: "COO" },
  { value: "chro", label: "CHRO" },
  { value: "cio", label: "CIO" },
];

function defaultPeriod(): string {
  const now = new Date();
  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** Admin actions strip: seed the registry, snapshot current values, check alerts. */
export function ScorecardActions() {
  const canManage = useCanManageAnalytics();
  const setup = useEnsureSetup();
  const snapshot = useSnapshot();
  const alerts = useCheckAlerts();

  if (!canManage) return null;

  async function doSetup() {
    try {
      const res = await setup.mutateAsync();
      toast.success(`${res.detail || "Analytics setup complete"} (${res.created} created)`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not run setup");
    }
  }
  async function doSnapshot() {
    try {
      const res = await snapshot.mutateAsync(defaultPeriod());
      toast.success(`Snapshotted ${res.snapshotted} KPI${res.snapshotted === 1 ? "" : "s"}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not snapshot");
    }
  }
  async function doAlerts() {
    try {
      const res = await alerts.mutateAsync();
      const n = res.alerts.length;
      if (n === 0) toast.success("No KPIs in warning or critical");
      else toast.info(`${n} KPI${n === 1 ? "" : "s"} need attention`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not check alerts");
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" onClick={doSetup} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
      <Button variant="outline" size="sm" onClick={doSnapshot} disabled={snapshot.isPending}>
        {snapshot.isPending ? "Snapshotting…" : "Snapshot now"}
      </Button>
      <Button variant="outline" size="sm" onClick={doAlerts} disabled={alerts.isPending}>
        {alerts.isPending ? "Checking…" : "Check alerts"}
      </Button>
    </div>
  );
}

function SummaryCounts({ summary }: { summary: ScorecardSummary }) {
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <Badge variant="success">{summary.good} good</Badge>
      <Badge variant="warning">{summary.warning} warning</Badge>
      <Badge variant="destructive">{summary.critical} critical</Badge>
      <Badge variant="secondary">{summary.unknown} unknown</Badge>
    </div>
  );
}

/** Renders one role's scorecard: KPI cards + summary counts. */
export function RoleScorecard({ role }: { role: ScorecardRole }) {
  const sc = useScorecard(role);

  if (sc.isLoading) return <Skeleton className="h-48 w-full" />;
  if (sc.isError) return <ErrorState title="Couldn't load scorecard" />;

  const data = sc.data;
  const kpis = data?.kpis ?? [];

  return (
    <div className="space-y-3">
      {data && <SummaryCounts summary={data.summary} />}
      {kpis.length === 0 ? (
        <EmptyState
          title="No KPIs for this role"
          description="Run setup to seed the standard KPI registry, then assign KPIs to roles."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {kpis.map((k) => (
            <li key={k.code}>
              <KpiCard kpi={k} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Executive scorecard with a role switcher + admin actions (the analytics overview). */
export function ScorecardView() {
  const [role, setRole] = useState<ScorecardRole>("ceo");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-48">
          <label htmlFor="sc-role" className="text-xs uppercase tracking-wide text-muted-foreground">
            Executive role
          </label>
          <Select value={role} onValueChange={(v) => setRole(v as ScorecardRole)}>
            <SelectTrigger id="sc-role" aria-label="Executive role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCORECARD_ROLES.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <ScorecardActions />
      </div>
      <RoleScorecard role={role} />
    </div>
  );
}

/** All five role scorecards stacked (the /analytics/scorecards page). */
export function AllScorecards() {
  return (
    <div className="space-y-8">
      {SCORECARD_ROLES.map((r) => (
        <section key={r.value} className="space-y-3">
          <h2 className="text-lg font-medium">{r.label}</h2>
          <RoleScorecard role={r.value} />
        </section>
      ))}
    </div>
  );
}
