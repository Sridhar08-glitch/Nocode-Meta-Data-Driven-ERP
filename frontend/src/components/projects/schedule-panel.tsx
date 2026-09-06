"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { GanttBar, ProjectSchedule } from "@/lib/projects/api";
import { useProjectSchedule } from "@/lib/projects/hooks";

/** Native scheduling / critical-path panel (Phase P2.10) — enter a project record id, then view the
 * computed project duration, critical task ids, total float, and a simple gantt list. Scheduling math
 * (forward/backward pass, critical path) runs server-side. */
export function SchedulePanel() {
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
        <EmptyState title="Enter a project record id" description="Load a project to see its critical path and gantt." />
      ) : (
        <ScheduleView projectRecordId={active} />
      )}
    </div>
  );
}

export function ScheduleView({ projectRecordId }: { projectRecordId: string }) {
  const sched = useProjectSchedule(projectRecordId);

  if (sched.isLoading) return <Skeleton className="h-40 w-full" />;
  if (sched.isError) return <ErrorState title="Couldn't load schedule" />;
  if (!sched.data) return null;

  const d: ProjectSchedule = sched.data;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Project duration" value={`${d.project_duration} days`} />
        <Metric label="Total float" value={`${d.total_float} days`} />
        <Metric label="Critical tasks" value={String(d.critical_task_ids.length)} />
        <Metric label="Earliest finish" value={d.earliest_finish ?? "—"} />
      </section>

      {d.critical_task_ids.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Critical path</h2>
          <ul className="flex flex-wrap gap-2">
            {d.critical_task_ids.map((id) => (
              <li key={id}>
                <Badge variant="destructive" className="font-mono">{id.slice(0, 8)}</Badge>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Gantt</h2>
        {d.gantt.length === 0 ? (
          <EmptyState title="No scheduled tasks" description="Add tasks with start/finish dates to build the gantt." />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Task</th>
                  <th className="px-3 py-2">Start</th>
                  <th className="px-3 py-2">Finish</th>
                  <th className="px-3 py-2 text-right">Float</th>
                  <th className="px-3 py-2">Critical</th>
                </tr>
              </thead>
              <tbody>
                {d.gantt.map((g: GanttBar) => (
                  <tr key={g.id} className="border-b last:border-0">
                    <td className="px-3 py-2 font-mono text-muted-foreground">{g.id.slice(0, 8)}</td>
                    <td className="px-3 py-2 font-mono">{g.start}</td>
                    <td className="px-3 py-2 font-mono">{g.finish}</td>
                    <td className="px-3 py-2 text-right font-mono">{g.float}</td>
                    <td className="px-3 py-2">
                      {g.critical ? <Badge variant="destructive">Critical</Badge> : <span className="text-muted-foreground">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1 rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
