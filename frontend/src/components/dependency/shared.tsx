"use client";

import { Badge } from "@/components/ui/badge";
import type { Dependent, RiskInfo, RiskLevel } from "@/lib/dependency/api";

/**
 * Friendly type→label map. This is presentation only — the SET of analyzable types stays
 * data-driven (from `/object-types/`); an unmapped type falls back to a humanized slug, so a
 * future backend type still renders correctly.
 */
const TYPE_LABELS: Record<string, string> = {
  entity: "Entity",
  field: "Field",
  report: "Report",
  dashboard: "Dashboard",
  kpi: "KPI",
  role: "Role",
  view: "View",
  workflow: "Workflow",
  rule: "Rule",
  form: "Form",
};

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const RISK_VARIANT: Record<RiskLevel, "secondary" | "warning" | "default" | "destructive"> = {
  low: "secondary",
  medium: "warning",
  high: "default",
  critical: "destructive",
};

/** Risk pill — grey / amber / orange / red per level, with the dependent count. */
export function RiskBadge({ risk }: { risk: RiskInfo }) {
  return (
    <Badge
      variant={RISK_VARIANT[risk.level] ?? "secondary"}
      className={risk.level === "high" ? "bg-orange-500 text-white" : undefined}
      aria-label={`Risk: ${risk.level}`}
    >
      {risk.level} risk · {risk.count}
    </Badge>
  );
}

/** Used-by count + dependents-by-type breakdown — a compact summary reused across surfaces. */
export function UsedBySummary({
  usedByCount,
  byType,
}: {
  usedByCount: number;
  byType: Record<string, number>;
}) {
  const entries = Object.entries(byType).filter(([, n]) => n > 0);
  return (
    <div className="space-y-1.5">
      <p className="text-sm">
        Used by <span className="font-semibold">{usedByCount}</span> object
        {usedByCount === 1 ? "" : "s"}.
      </p>
      {entries.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Dependents by type">
          {entries.map(([type, n]) => (
            <Badge key={type} variant="outline">
              {typeLabel(type)}: {n}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

/** Generic dependents list, grouped by type. Approximate (heuristic) matches are flagged. */
export function DependentsList({ dependents }: { dependents: Dependent[] }) {
  if (dependents.length === 0) {
    return <p className="text-sm text-muted-foreground">No dependents found.</p>;
  }
  const groups = new Map<string, Dependent[]>();
  for (const d of dependents) {
    const arr = groups.get(d.type) ?? [];
    arr.push(d);
    groups.set(d.type, arr);
  }
  return (
    <div className="space-y-3" aria-label="Dependents">
      {Array.from(groups.entries()).map(([type, items]) => (
        <div key={type} className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {typeLabel(type)} ({items.length})
          </p>
          <ul className="space-y-1.5">
            {items.map((d, i) => (
              <li
                key={`${d.type}-${d.id ?? i}`}
                className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm"
              >
                <span className="font-medium">{d.name}</span>
                <span className="text-xs text-muted-foreground">{d.detail}</span>
                {d.approximate && (
                  <Badge variant="outline" className="text-amber-600">
                    possible match
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
