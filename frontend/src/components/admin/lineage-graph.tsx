"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { LineageGraph, LineageNode } from "@/lib/lineage/api";
import { useDownstream, useLineageNodes, useUpstream } from "@/lib/lineage/hooks";

const nodeLabel = (n: LineageNode) => n.display_name || n.object_slug || `${n.node_type}:${n.object_id.slice(0, 8)}`;

/**
 * Data Lineage graph (Phase F3.3): pick a node → see its upstream sources and downstream
 * consumers. Dependency-free layout (upstream | node | downstream) — consistent with the
 * no-heavy-graph-dep precedent (F1.8/F1.10); React Flow is intentionally not used.
 */
export function LineageGraphPanel() {
  const [typeFilter, setTypeFilter] = useState("");
  const nodes = useLineageNodes(typeFilter.trim() || undefined);
  const [selected, setSelected] = useState<LineageNode | null>(null);

  const upstream = useUpstream(selected?.id ?? null);
  const downstream = useDownstream(selected?.id ?? null);

  const rows = nodes.data?.results ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
      <aside className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="ln-type">Filter by type</Label>
          <Input id="ln-type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} placeholder="entity, report, workflow…" className="h-9" />
        </div>
        {nodes.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : nodes.isError ? (
          <ErrorState title="Couldn't load nodes" />
        ) : rows.length === 0 ? (
          <EmptyState title="No lineage nodes" description="Nodes appear as records, reports, and workflows reference data." className="border-0 p-0 text-left" />
        ) : (
          <ul className="max-h-[28rem] space-y-1 overflow-y-auto">
            {rows.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  aria-label={`Select ${nodeLabel(n)}`}
                  onClick={() => setSelected(n)}
                  className={`flex w-full flex-col items-start gap-0.5 rounded-md border p-2 text-left text-sm transition-colors hover:bg-accent ${selected?.id === n.id ? "border-primary bg-primary/5" : ""}`}
                >
                  <span className="font-medium">{nodeLabel(n)}</span>
                  <Badge variant="outline">{n.node_type}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section>
        {!selected ? (
          <EmptyState title="Select a node" description="Pick a node on the left to see what feeds it and what it feeds." />
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            <LineageColumn title="Upstream" hint="feeds into" query={upstream} excludeId={selected.id} />
            <div className="flex items-center justify-center">
              <div className="rounded-lg border-2 border-primary p-4 text-center" aria-label="Selected node">
                <div className="font-medium">{nodeLabel(selected)}</div>
                <Badge variant="outline" className="mt-1">{selected.node_type}</Badge>
              </div>
            </div>
            <LineageColumn title="Downstream" hint="consumed by" query={downstream} excludeId={selected.id} />
          </div>
        )}
      </section>
    </div>
  );
}

function LineageColumn({
  title,
  hint,
  query,
  excludeId,
}: {
  title: string;
  hint: string;
  query: { isLoading: boolean; isError: boolean; data?: LineageGraph };
  excludeId: string;
}) {
  const others = (query.data?.nodes ?? []).filter((n) => n.id !== excludeId);
  return (
    <div className="space-y-2" aria-label={`${title.toLowerCase()} nodes`}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title} <span className="font-normal lowercase">({hint})</span>
      </h3>
      {query.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : query.isError ? (
        <ErrorState title={`Couldn't load ${title.toLowerCase()}`} />
      ) : others.length === 0 ? (
        <p className="text-xs text-muted-foreground">None.</p>
      ) : (
        <ul className="space-y-1.5">
          {others.map((n) => (
            <li key={n.id} className="rounded-md border p-2 text-sm">
              <span className="font-medium">{nodeLabel(n)}</span>
              <Badge variant="outline" className="ml-2">{n.node_type}</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
