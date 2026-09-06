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
import type {
  ChangePreviewResult,
  DependencyGraph,
  GraphNode,
  PromotionObjectInput,
  PromotionPrecheckResult,
  RiskLevel,
} from "@/lib/dependency/api";
import {
  useAnalyze,
  useChangePreview,
  useDependencyGraph,
  useExecutiveSummary,
  useObjectTypes,
  usePromotionPrecheck,
  useSafeDelete,
} from "@/lib/dependency/hooks";

import { DependentsList, RiskBadge, typeLabel, UsedBySummary } from "./shared";

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Type Select (data-driven from `/object-types/`) + an object-id input. */
export function ObjectPicker({
  type,
  id,
  onType,
  onId,
}: {
  type: string;
  id: string;
  onType: (t: string) => void;
  onId: (v: string) => void;
}) {
  const types = useObjectTypes();
  const options = types.data?.object_types ?? [];
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1.5">
        <Label htmlFor="dep-type">Object type</Label>
        <Select value={type || undefined} onValueChange={onType}>
          <SelectTrigger id="dep-type" aria-label="Object type" className="w-48">
            <SelectValue placeholder={types.isLoading ? "Loading…" : "Select type"} />
          </SelectTrigger>
          <SelectContent>
            {options.map((t) => (
              <SelectItem key={t} value={t}>
                {typeLabel(t)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="dep-id">Object id / slug</Label>
        <Input
          id="dep-id"
          value={id}
          onChange={(e) => onId(e.target.value)}
          placeholder="uuid or slug"
          className="w-64"
        />
      </div>
    </div>
  );
}

/** Used-by view: analyze → count + risk + grouped dependents. */
export function UsedByView({ type, id }: { type: string | null; id: string | null }) {
  const q = useAnalyze(type, id);
  if (!type || !id) {
    return <EmptyState className="border-0 p-0 text-left" title="Pick an object above to analyze it." />;
  }
  if (q.isLoading) return <Skeleton className="h-32 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't analyze this object" />;
  const a = q.data!;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{a.name || `${typeLabel(a.object_type)} ${a.object_id}`}</span>
        <RiskBadge risk={a.risk} />
        {a.risk.has_automation && <Badge variant="warning">automation</Badge>}
      </div>
      <UsedBySummary usedByCount={a.used_by_count} byType={a.by_type} />
      <DependentsList dependents={a.dependents} />
    </div>
  );
}

const indent = (n: number) => ({ paddingLeft: `${n * 1.25}rem` });

/** Dependency graph as a readable indented adjacency list (no heavy graph lib). */
export function GraphView({ type, id }: { type: string | null; id: string | null }) {
  const q = useDependencyGraph(type, id);
  if (!type || !id) {
    return <EmptyState className="border-0 p-0 text-left" title="Pick an object above." />;
  }
  if (q.isLoading) return <Skeleton className="h-32 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't load the dependency graph" />;
  const g = q.data as DependencyGraph;
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  // adjacency: node → its outgoing edges
  const out = new Map<string, { to: GraphNode; detail: string }[]>();
  for (const e of g.edges) {
    const target = byId.get(e.to);
    if (!target) continue;
    const arr = out.get(e.from) ?? [];
    arr.push({ to: target, detail: e.detail });
    out.set(e.from, arr);
  }
  const label = (n: GraphNode) => n.name || `${typeLabel(n.object_type)} ${n.object_id.slice(0, 8)}`;
  if (g.nodes.length === 0) {
    return <p className="text-sm text-muted-foreground">No graph data.</p>;
  }
  return (
    <ul className="space-y-1" aria-label="Dependency graph">
      {g.nodes.map((n) => {
        const children = out.get(n.id) ?? [];
        return (
          <li key={n.id} className="text-sm">
            <div className="flex items-center gap-2 rounded-md border p-2">
              <Badge variant="outline">{typeLabel(n.object_type)}</Badge>
              <span className="font-medium">{label(n)}</span>
              {n.approximate && <span className="text-xs text-amber-600">(approx)</span>}
            </div>
            {children.length > 0 && (
              <ul className="mt-1 space-y-1">
                {children.map((c, i) => (
                  <li key={`${n.id}-${c.to.id}-${i}`} style={indent(1)} className="text-xs text-muted-foreground">
                    → {label(c.to)} <span className="opacity-70">({c.detail})</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Safe-delete: analyze + a safe/unsafe verdict. */
export function SafeDeleteView({ type, id }: { type: string | null; id: string | null }) {
  const q = useSafeDelete(type, id);
  if (!type || !id) {
    return <EmptyState className="border-0 p-0 text-left" title="Pick an object above." />;
  }
  if (q.isLoading) return <Skeleton className="h-24 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't run the safe-delete check" />;
  const r = q.data!;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={r.safe ? "success" : "destructive"}>{r.safe ? "Safe to delete" : "Not safe"}</Badge>
        <RiskBadge risk={r.risk} />
      </div>
      <p className="text-sm text-muted-foreground">{r.message}</p>
      <UsedBySummary usedByCount={r.used_by_count} byType={r.by_type} />
    </div>
  );
}

/** Change preview: enter type+id + a change description → direct/indirect impact + risk. */
export function ChangePreviewPanel() {
  const [type, setType] = useState("");
  const [id, setId] = useState("");
  const [changeText, setChangeText] = useState("");
  const [result, setResult] = useState<ChangePreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const preview = useChangePreview();

  async function run() {
    setError(null);
    let change: Record<string, unknown> = {};
    if (changeText.trim()) {
      try {
        change = JSON.parse(changeText);
      } catch {
        setError("Change must be valid JSON (e.g. {\"field\":\"status\",\"op\":\"rename\"}).");
        return;
      }
    }
    const r = await preview.mutateAsync({ object_type: type, object_id: id, change });
    setResult(r);
  }

  return (
    <div className="space-y-3">
      <ObjectPicker type={type} id={id} onType={setType} onId={setId} />
      <div className="space-y-1.5">
        <Label htmlFor="cp-change">Change (JSON, optional)</Label>
        <Input
          id="cp-change"
          value={changeText}
          onChange={(e) => setChangeText(e.target.value)}
          placeholder='{"op":"rename"}'
          className="w-full"
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button onClick={run} disabled={!type || !id || preview.isPending}>
        {preview.isPending ? "Previewing…" : "Preview impact"}
      </Button>
      {result && (
        <div className="space-y-2 rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-3">
            <RiskBadge risk={result.risk} />
            <span className="text-sm">
              Direct: <span className="font-semibold">{result.direct_impact}</span> · Indirect:{" "}
              <span className="font-semibold">{result.indirect_impact}</span>
            </span>
          </div>
          <DependentsList dependents={result.direct} />
        </div>
      )}
    </div>
  );
}

const RISK_ORDER: RiskLevel[] = ["critical", "high", "medium", "low"];

/** Promotion precheck (admin): add {type,id} rows → decision + per-object risk + summary. */
export function PromotionPrecheckPanel() {
  const types = useObjectTypes();
  const options = types.data?.object_types ?? [];
  const [rows, setRows] = useState<PromotionObjectInput[]>([{ object_type: "", object_id: "" }]);
  const [result, setResult] = useState<PromotionPrecheckResult | null>(null);
  const precheck = usePromotionPrecheck();

  function setRow(i: number, patch: Partial<PromotionObjectInput>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  const valid = rows.filter((r) => r.object_type && r.object_id);

  const summary: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0, critical: 0 };
  for (const o of result?.objects ?? []) summary[o.risk.level] = (summary[o.risk.level] ?? 0) + 1;

  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {rows.map((r, i) => (
          <li key={i} className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor={`pp-type-${i}`}>Type</Label>
              <Select value={r.object_type || undefined} onValueChange={(v) => setRow(i, { object_type: v })}>
                <SelectTrigger id={`pp-type-${i}`} aria-label={`Promotion object ${i + 1} type`} className="w-44">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  {options.map((t) => (
                    <SelectItem key={t} value={t}>
                      {typeLabel(t)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Input
              aria-label={`Promotion object ${i + 1} id`}
              value={r.object_id}
              onChange={(e) => setRow(i, { object_id: e.target.value })}
              placeholder="id / slug"
              className="w-56"
            />
            {rows.length > 1 && (
              <Button variant="ghost" size="sm" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>
                Remove
              </Button>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => setRows((rs) => [...rs, { object_type: "", object_id: "" }])}>
          Add object
        </Button>
        <Button
          onClick={async () => setResult(await precheck.mutateAsync(valid))}
          disabled={valid.length === 0 || precheck.isPending}
        >
          {precheck.isPending ? "Checking…" : "Run precheck"}
        </Button>
      </div>
      {result && (
        <div className="space-y-3 rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={result.blocked ? "destructive" : "success"}>
              {result.blocked ? "Blocked" : "Allowed"}
            </Badge>
            <span className="text-sm text-muted-foreground">{result.decision}</span>
          </div>
          <div className="flex flex-wrap gap-1.5" aria-label="Risk summary">
            {RISK_ORDER.filter((lvl) => summary[lvl] > 0).map((lvl) => (
              <Badge key={lvl} variant="outline">
                {lvl}: {summary[lvl]}
              </Badge>
            ))}
          </div>
          <ul className="space-y-1.5">
            {result.objects.map((o, i) => (
              <li key={`${o.object_type}-${o.object_id}-${i}`} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
                <Badge variant="outline">{typeLabel(o.object_type)}</Badge>
                <span className="font-medium">{o.name || o.object_id}</span>
                <span className="text-xs text-muted-foreground">used by {o.used_by_count}</span>
                <RiskBadge risk={o.risk} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Executive summary (admin): totals + high-risk count + recent analyses. */
export function ExecutiveSummaryCard() {
  const q = useExecutiveSummary();
  if (q.isLoading || !q.data) return <Skeleton className="h-32 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't load the executive summary" />;
  const s = q.data;
  const totals: [string, number][] = [
    ["Entities", s.totals.entities],
    ["Fields", s.totals.fields],
    ["Reports", s.totals.reports],
    ["Dashboards", s.totals.dashboards],
    ["Workflows", s.totals.workflows],
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {totals.map(([label, n]) => (
          <div key={label} className="rounded-md border p-3">
            <div className="text-2xl font-semibold">{n}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
        <div className="rounded-md border p-3">
          <div className="text-2xl font-semibold text-destructive">{s.high_risk_recent}</div>
          <div className="text-xs text-muted-foreground">High-risk recent</div>
        </div>
      </div>
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent analyses</h3>
        {s.recent_analyses.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent analyses.</p>
        ) : (
          <ul className="space-y-1.5">
            {s.recent_analyses.map((r, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
                <Badge variant="outline">{typeLabel(r.object_type)}</Badge>
                <span className="text-xs text-muted-foreground">used by {r.used_by}</span>
                <Badge variant={r.risk === "critical" || r.risk === "high" ? "destructive" : "secondary"}>
                  {r.risk}
                </Badge>
                <span className="ml-auto text-xs text-muted-foreground">{r.at}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/**
 * Dependency & Impact Analysis console (Phase P2.14). Member surfaces: used-by, graph,
 * change-preview, safe-delete. Admin surfaces (promotion precheck + executive summary) gate on role.
 */
export function DependencyConsole({ isAdmin }: { isAdmin: boolean }) {
  const [type, setType] = useState("");
  const [id, setId] = useState("");

  return (
    <div className="space-y-6">
      <Section title="Object" description="Choose any analyzable object — the type list is loaded from the API.">
        <ObjectPicker type={type} id={id} onType={setType} onId={setId} />
      </Section>

      <Section title="Used by" description="Everything that references this object, grouped by type.">
        <UsedByView type={type || null} id={id || null} />
      </Section>

      <Section title="Dependency graph" description="Reachable dependents as an indented adjacency list.">
        <GraphView type={type || null} id={id || null} />
      </Section>

      <Section title="Safe delete" description="Whether removing this object is safe.">
        <SafeDeleteView type={type || null} id={id || null} />
      </Section>

      <Section title="Change preview" description="Estimate the blast radius of a proposed change.">
        <ChangePreviewPanel />
      </Section>

      {isAdmin && (
        <Section
          title="Promotion precheck"
          description="Gate a set of objects before promoting them (admin)."
        >
          <PromotionPrecheckPanel />
        </Section>
      )}

      {isAdmin && (
        <Section title="Executive summary" description="Workspace-wide impact totals and recent activity (admin).">
          <ExecutiveSummaryCard />
        </Section>
      )}
    </div>
  );
}
