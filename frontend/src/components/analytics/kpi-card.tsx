"use client";

import { Badge } from "@/components/ui/badge";
import type { KpiStatus, KpiValue } from "@/lib/analytics/api";
import { cn } from "@/lib/utils";

/** good=green, warning=amber, critical=red, unknown=grey. */
export const KPI_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
  good: "success",
  warning: "warning",
  critical: "destructive",
  unknown: "secondary",
};

const KPI_STATUS_BORDER: Record<string, string> = {
  good: "border-l-success",
  warning: "border-l-warning",
  critical: "border-l-destructive",
  unknown: "border-l-border",
};

function fmt(v: number | string | null): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

/** A single KPI tile: name, current value + unit, target, and a status badge. */
export function KpiCard({ kpi }: { kpi: KpiValue }) {
  const status = (kpi.status as KpiStatus) ?? "unknown";
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-2 rounded-lg border border-l-4 p-4",
        KPI_STATUS_BORDER[status] ?? KPI_STATUS_BORDER.unknown,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-tight">{kpi.name}</span>
        <Badge variant={KPI_STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-semibold tabular-nums">
          {kpi.available ? fmt(kpi.value) : "—"}
        </span>
        {kpi.unit && kpi.available && (
          <span className="text-sm text-muted-foreground">{kpi.unit}</span>
        )}
      </div>
      <div className="mt-auto flex items-center justify-between text-xs text-muted-foreground">
        <span>Target {fmt(kpi.target)}{kpi.unit && kpi.target !== null ? ` ${kpi.unit}` : ""}</span>
        {kpi.variance !== null && kpi.variance !== undefined && kpi.available && (
          <span className="tabular-nums">Δ {fmt(kpi.variance)}</span>
        )}
      </div>
    </div>
  );
}
