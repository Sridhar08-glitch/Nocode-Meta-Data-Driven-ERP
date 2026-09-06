"use client";

import { Badge } from "@/components/ui/badge";
import type {
  PackageDiff,
  PackageStatus,
  RiskLevel,
  RiskSummary,
} from "@/lib/environments/api";

const DIFF_KINDS = ["entities", "fields", "rules", "roles", "permissions"] as const;
const RISK_ORDER: RiskLevel[] = ["critical", "high", "medium", "low"];

export function shortHash(h: string | null | undefined) {
  return h ? h.slice(0, 8) : "—";
}

/** Color-coded risk chip: grey/amber/orange/red for low/medium/high/critical. */
export function RiskBadge({ level, count }: { level: RiskLevel; count?: number }) {
  const cls: Record<RiskLevel, string> = {
    low: "bg-muted text-muted-foreground border-transparent",
    medium: "bg-amber-500 text-white border-transparent",
    high: "bg-orange-600 text-white border-transparent",
    critical: "bg-red-600 text-white border-transparent",
  };
  return (
    <Badge aria-label={`Risk: ${level}`} className={cls[level]}>
      {level}
      {count !== undefined ? `: ${count}` : ""}
    </Badge>
  );
}

/** Render the risk_summary as one chip per non-zero level (critical first). */
export function RiskSummaryBadges({ risk }: { risk: RiskSummary | undefined }) {
  const r = risk ?? {};
  const chips = RISK_ORDER.filter((lvl) => (r[lvl] ?? 0) > 0);
  return (
    <span className="flex flex-wrap items-center gap-1.5" aria-label="Risk summary">
      {chips.length === 0 ? (
        <span className="text-xs text-muted-foreground">no risk</span>
      ) : (
        chips.map((lvl) => <RiskBadge key={lvl} level={lvl} count={r[lvl]} />)
      )}
      {(r.blocked ?? 0) > 0 && (
        <Badge variant="destructive" aria-label="Blocked by precheck">
          blocked: {r.blocked}
        </Badge>
      )}
    </span>
  );
}

const STATUS_VARIANT: Record<
  PackageStatus,
  "default" | "secondary" | "destructive" | "success" | "warning" | "outline"
> = {
  draft: "outline",
  precheck: "secondary",
  approved: "warning",
  executed: "success",
  failed: "destructive",
  rolled_back: "secondary",
};

export function StatusBadge({ status }: { status: PackageStatus }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"} aria-label={`Status: ${status}`}>
      {status.replace("_", " ")}
    </Badge>
  );
}

function labelOf(obj: unknown): string {
  if (obj && typeof obj === "object") {
    const o = obj as Record<string, unknown> & { after?: Record<string, unknown> };
    const src = o.after && typeof o.after === "object" ? o.after : o;
    return String(src.slug ?? src.name ?? src.id ?? JSON.stringify(src).slice(0, 40));
  }
  return String(obj);
}

/** Lightweight structural diff (mirrors the config-vcs panel's renderer). */
export function DiffSummary({ diff }: { diff: PackageDiff | undefined }) {
  if (!diff) return <p className="text-sm text-muted-foreground">No diff available.</p>;
  const kinds = DIFF_KINDS.filter((k) => {
    const d = diff[k];
    return d && (d.added.length || d.removed.length || d.modified.length);
  });
  if (kinds.length === 0) {
    return <p className="text-sm text-muted-foreground">No configuration differences.</p>;
  }
  return (
    <div className="space-y-3">
      {kinds.map((kind) => {
        const d = diff[kind];
        return (
          <div key={kind} className="rounded-md border p-3" aria-label={`diff-${kind}`}>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium capitalize">
              {kind}
              {d.added.length > 0 && <Badge className="bg-emerald-600">+{d.added.length}</Badge>}
              {d.removed.length > 0 && <Badge variant="destructive">−{d.removed.length}</Badge>}
              {d.modified.length > 0 && <Badge variant="secondary">~{d.modified.length}</Badge>}
            </div>
            <ul className="space-y-0.5 text-xs">
              {d.added.map((o, i) => (
                <li key={`a${i}`} className="text-emerald-600">
                  + {labelOf(o)}
                </li>
              ))}
              {d.removed.map((o, i) => (
                <li key={`r${i}`} className="text-destructive">
                  − {labelOf(o)}
                </li>
              ))}
              {d.modified.map((o, i) => (
                <li key={`m${i}`} className="text-muted-foreground">
                  ~ {labelOf(o)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
