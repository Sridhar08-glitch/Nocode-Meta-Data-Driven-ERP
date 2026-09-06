"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type {
  ResourceCapacityRow,
  ResourceUtilizationRow,
} from "@/lib/projects/api";
import { useResourceCapacity, useResourceUtilization } from "@/lib/projects/hooks";

/** Native resourcing panel (Phase P2.10) — workspace-wide resource utilization, allocation conflicts,
 * and weekly capacity (allocated vs available hours). All resourcing math runs server-side. */
export function ResourcesPanel() {
  return (
    <div className="space-y-6">
      <UtilizationTable />
      <CapacityTable />
    </div>
  );
}

export function UtilizationTable() {
  const util = useResourceUtilization();

  if (util.isLoading) return <Skeleton className="h-40 w-full" />;
  if (util.isError) return <ErrorState title="Couldn't load utilization" />;

  const rows = util.data?.utilization ?? [];
  const conflicts = util.data?.conflicts ?? [];

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">Utilization</h2>

      {conflicts.length > 0 && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <p className="font-medium text-destructive">{conflicts.length} allocation conflict{conflicts.length === 1 ? "" : "s"}</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {conflicts.map((c, i) => (
              <li key={`${c.employee}-${i}`}>
                <Badge variant="destructive" className="font-mono">{c.employee.slice(0, 8)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rows.length === 0 ? (
        <EmptyState title="No utilization data" description="Allocate project members to see utilization." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Employee</th>
                <th className="px-3 py-2 text-right">Allocated</th>
                <th className="px-3 py-2 text-right">Available</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: ResourceUtilizationRow, i) => (
                <tr key={`${r.employee}-${i}`} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{r.employee.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.total_percent}%</td>
                  <td className="px-3 py-2 text-right font-mono">{r.available_percent}%</td>
                  <td className="px-3 py-2">
                    {r.over_allocated ? (
                      <Badge variant="destructive">Over-allocated</Badge>
                    ) : (
                      <Badge variant="secondary">OK</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function CapacityTable() {
  const [weeklyHours, setWeeklyHours] = useState("40");
  const [hours, setHours] = useState(40);
  const cap = useResourceCapacity(hours);

  function apply() {
    const n = Number(weeklyHours);
    if (Number.isFinite(n) && n > 0) setHours(n);
  }

  const rows = cap.data?.capacity ?? [];

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-sm font-medium">Capacity</h2>
        <div className="flex items-end gap-2">
          <label className="w-40 space-y-1">
            <span className="text-xs font-medium">Weekly hours</span>
            <Input
              aria-label="Weekly hours"
              inputMode="numeric"
              value={weeklyHours}
              onChange={(e) => setWeeklyHours(e.target.value)}
            />
          </label>
          <Button variant="outline" onClick={apply}>
            Apply
          </Button>
        </div>
      </div>

      {cap.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : cap.isError ? (
        <ErrorState title="Couldn't load capacity" />
      ) : rows.length === 0 ? (
        <EmptyState title="No capacity data" description="Allocate project members to see capacity." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Employee</th>
                <th className="px-3 py-2 text-right">Allocated hours</th>
                <th className="px-3 py-2 text-right">Available hours</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: ResourceCapacityRow, i) => (
                <tr key={`${r.employee}-${i}`} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{r.employee.slice(0, 8)}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.allocated_hours}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.available_hours}</td>
                  <td className="px-3 py-2">
                    {r.over_capacity ? (
                      <Badge variant="destructive">Over capacity</Badge>
                    ) : (
                      <Badge variant="secondary">OK</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
