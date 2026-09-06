"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { KpiValue } from "@/lib/analytics/api";
import { useEvaluateAll } from "@/lib/analytics/hooks";

import { KpiCard } from "./kpi-card";

function groupByCategory(values: KpiValue[]): [string, KpiValue[]][] {
  const map = new Map<string, KpiValue[]>();
  for (const v of values) {
    const cat = v.category || "Uncategorized";
    const list = map.get(cat) ?? [];
    list.push(v);
    map.set(cat, list);
  }
  return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
}

/** ERP health: evaluate-all KPIs grouped by category — a module-by-module health grid. */
export function HealthGrid() {
  const evalAll = useEvaluateAll();

  if (evalAll.isLoading) return <Skeleton className="h-64 w-full" />;
  if (evalAll.isError) return <ErrorState title="Couldn't evaluate KPIs" />;

  const values = evalAll.data ?? [];
  if (values.length === 0) {
    return (
      <EmptyState
        title="No KPIs to evaluate"
        description="Run setup on the scorecard to seed the standard KPI registry."
      />
    );
  }

  const groups = groupByCategory(values);

  return (
    <div className="space-y-6">
      {groups.map(([category, kpis]) => (
        <section key={category} className="space-y-3">
          <h2 className="text-lg font-medium capitalize">{category}</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {kpis.map((k) => (
              <li key={k.code}>
                <KpiCard kpi={k} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
