"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { RiskBadge, UsedBySummary } from "@/components/dependency/shared";
import type { AnalyzeResult } from "@/lib/dependency/api";
import type { ImpactResult } from "@/lib/metadata/builder-api";

/**
 * Pre-delete impact check (Phase P1.4, enriched in P2.14). Fetches the config objects that
 * reference the entity/field being deleted and warns before confirming. Deletes are soft
 * (recoverable), so we WARN rather than hard-block — but the admin sees exactly what may break.
 *
 * P2.14: when an optional `analyzeFetcher` is supplied (the `/dependency/analyze/` result), the
 * dialog additionally surfaces a risk badge + used-by-count + by-type breakdown. This is purely
 * additive — the original entity/field delete-impact behavior and props are unchanged.
 */
export function ImpactWarningDialog({
  open,
  title,
  queryKey,
  fetcher,
  onConfirm,
  onCancel,
  confirmLabel = "Delete anyway",
  busyLabel = "Removing…",
  busy = false,
  note,
  analyzeQueryKey,
  analyzeFetcher,
}: {
  open: boolean;
  title: string;
  queryKey: unknown[];
  fetcher: () => Promise<ImpactResult>;
  onConfirm: () => void;
  onCancel: () => void;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  note?: string;
  /** Optional: query key for the `/dependency/analyze/` enrichment (risk + used-by). */
  analyzeQueryKey?: unknown[];
  /** Optional: fetches the analyze result to enrich the dialog with a risk badge + summary. */
  analyzeFetcher?: () => Promise<AnalyzeResult>;
}) {
  const impact = useQuery({ queryKey, queryFn: fetcher, enabled: open });
  const deps = impact.data?.dependents ?? [];

  const analyze = useQuery({
    queryKey: analyzeQueryKey ?? ["__impact-analyze-disabled__"],
    queryFn: analyzeFetcher ?? (() => Promise.reject(new Error("no analyzer"))),
    enabled: open && !!analyzeFetcher,
  });
  const analysis = analyze.data;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        {note && <p className="text-sm text-muted-foreground">{note}</p>}
        {analysis && (
          <div className="space-y-2 rounded-md border bg-muted/30 p-3" aria-label="Risk analysis">
            <RiskBadge risk={analysis.risk} />
            <UsedBySummary usedByCount={analysis.used_by_count} byType={analysis.by_type} />
          </div>
        )}
        {impact.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : impact.isError ? (
          <p className="text-sm text-muted-foreground">Couldn&apos;t check impact — proceed with caution.</p>
        ) : deps.length === 0 ? (
          <p className="text-sm text-muted-foreground">No known references. This is safe to remove.</p>
        ) : (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-destructive">
              This is referenced by {deps.length} configuration object(s). Removing it may break them:
            </p>
            <ul aria-label="Impact dependents" className="max-h-60 space-y-1.5 overflow-y-auto">
              {deps.map((d, i) => (
                <li key={`${d.type}-${d.id ?? i}`} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
                  <Badge variant="outline">{d.type.replace(/_/g, " ")}</Badge>
                  <span className="font-medium">{d.name}</span>
                  <span className="text-xs text-muted-foreground">{d.detail}{d.approximate ? " (possible match)" : ""}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={busy || impact.isLoading}>
            {busy ? busyLabel : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
