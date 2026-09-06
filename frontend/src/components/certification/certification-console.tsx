"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type {
  IntegrationStatus,
  SimulationResult,
} from "@/lib/certification/api";
import {
  useArchitectureValidation,
  useCertificationReport,
  useChecklist,
  useIntegrationRegistry,
  useModuleHealth,
  useReadiness,
  useRunAllScenarios,
  useRunScenario,
  useScenarios,
} from "@/lib/certification/hooks";

/** Map every status vocabulary the certification API uses onto a badge variant. */
type Variant = "success" | "warning" | "destructive" | "secondary";
const STATUS_VARIANT: Record<string, Variant> = {
  // health
  healthy: "success",
  warning: "warning",
  failed: "destructive",
  // architecture
  verified: "success",
  // readiness
  active: "success",
  ready: "warning",
  not_installed: "secondary",
  // integration
  certified: "success",
  partial: "warning",
  deferred: "secondary",
  // simulation/compliance
  passed: "success",
  skipped: "secondary",
  pending: "secondary",
  pass: "success",
  // honest item status vocabulary
  COMPLETE: "success",
  PARTIAL: "warning",
  NOT_IMPLEMENTED: "destructive",
  OUT_OF_SCOPE: "secondary",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "secondary"} aria-label={`Status: ${status}`}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

function Section({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const VERDICT_LABEL: Record<string, string> = {
  ENTERPRISE_CERTIFIED: "Enterprise certified",
  READY_WITH_WARNINGS: "Ready with warnings",
  NEEDS_ATTENTION: "Needs attention",
};
const VERDICT_VARIANT: Record<string, Variant> = {
  ENTERPRISE_CERTIFIED: "success",
  READY_WITH_WARNINGS: "warning",
  NEEDS_ATTENTION: "destructive",
};

// ── Overview / report ──────────────────────────────────────────────────────────

export function CertificationOverview() {
  const { data, isLoading, isError, refetch } = useCertificationReport();
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load the certification report." />;

  return (
    <Section
      title="Certification report"
      description={`Generated ${new Date(data.generated_at).toLocaleString()}`}
      action={
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Refresh
        </Button>
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={VERDICT_VARIANT[data.verdict] ?? "secondary"} className="text-sm">
          {VERDICT_LABEL[data.verdict] ?? data.verdict}
        </Badge>
        <span className="text-sm">
          Readiness score: <span className="font-semibold">{data.overall_readiness_score}%</span>
        </span>
        <span className="text-sm">
          Module readiness: <span className="font-semibold">{data.readiness_pct}%</span>
        </span>
        <StatusBadge status={data.overall_health} />
      </div>

      {data.status_counts && (
        <div className="flex flex-wrap gap-2" aria-label="Module status counts">
          {(["COMPLETE", "PARTIAL", "NOT_IMPLEMENTED", "OUT_OF_SCOPE"] as const).map((s) =>
            data.status_counts![s] ? (
              <span key={s} className="flex items-center gap-1.5 text-xs">
                <StatusBadge status={s} />
                <span className="font-semibold">{data.status_counts![s]}</span>
              </span>
            ) : null,
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.sections.map((s) => (
          <div key={s.name} className="rounded-md border p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {s.name}
            </p>
            <p className="mt-1 text-sm">
              <span className="font-semibold">{s.passed}</span> / {s.total} ({s.compliance_pct}%)
            </p>
          </div>
        ))}
      </div>

      {data.recommendations.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Recommendations
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm">
            {data.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

// ── Module health ────────────────────────────────────────────────────────────

const HEALTH_OMIT = new Set(["status", "note"]);

export function ModuleHealthGrid() {
  const { data, isLoading, isError } = useModuleHealth();
  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load module health." />;

  return (
    <Section
      title="Operational health"
      description="Live subsystem checks — read from existing engines, never a new one."
      action={<StatusBadge status={data.overall} />}
    >
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(data.modules).map(([name, info]) => {
          const metrics = Object.entries(info).filter(([k]) => !HEALTH_OMIT.has(k));
          return (
            <li key={name} className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{humanize(name)}</span>
                <StatusBadge status={String(info.status)} />
              </div>
              <dl className="space-y-0.5 text-xs text-muted-foreground">
                {metrics.map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt>{humanize(k)}</dt>
                    <dd className="font-mono text-foreground">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

// ── Executive readiness ─────────────────────────────────────────────────────

export function ReadinessGrid() {
  const { data, isLoading, isError } = useReadiness();
  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load readiness." />;

  return (
    <Section
      title="Executive readiness"
      description={`${data.ready_or_active} of ${data.total_modules} ERP modules ready or active`}
      action={<Badge variant="secondary">{data.readiness_pct}%</Badge>}
    >
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(data.modules).map(([name, info]) => (
          <li
            key={name}
            className="flex items-center justify-between gap-2 rounded-md border p-2.5 text-sm"
          >
            <span className="font-medium">{humanize(name)}</span>
            <span className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{info.activity_7d} events/7d</span>
              <StatusBadge status={info.status} />
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

// ── Architecture validation ──────────────────────────────────────────────────

export function ArchitectureValidationPanel() {
  const { data, isLoading, isError } = useArchitectureValidation();
  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not validate architecture." />;

  return (
    <Section
      title="Architecture validation"
      description="Each critical engine must exist in exactly one location (no duplicates)."
      action={
        <Badge variant={data.overall === "verified" ? "success" : "warning"}>
          {data.verified_count}/{data.total_engines} verified
        </Badge>
      }
    >
      <ul className="space-y-1.5">
        {Object.entries(data.engines).map(([name, info]) => (
          <li
            key={name}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm"
          >
            <span className="font-medium">{humanize(name)}</span>
            <code className="text-xs text-muted-foreground">{info.location}</code>
            <StatusBadge status={info.status} />
          </li>
        ))}
      </ul>
    </Section>
  );
}

// ── Integration registry ─────────────────────────────────────────────────────

export function IntegrationRegistryPanel() {
  const { data, isLoading, isError } = useIntegrationRegistry();
  const [filter, setFilter] = useState<IntegrationStatus | "all">("all");
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load the integration registry." />;

  const shown =
    filter === "all" ? data.integrations : data.integrations.filter((i) => i.status === filter);

  return (
    <Section
      title="Integration registry"
      description={`${data.certified_count} of ${data.total_integrations} cross-module integrations certified`}
      action={
        <div className="flex gap-1">
          {(["all", "certified", "partial", "deferred"] as const).map((f) => (
            <Button
              key={f}
              size="sm"
              variant={filter === f ? "default" : "outline"}
              onClick={() => setFilter(f)}
            >
              {f}
            </Button>
          ))}
        </div>
      }
    >
      {shown.length === 0 ? (
        <EmptyState title="No integrations" description="None match this filter." />
      ) : (
        <ul className="space-y-2">
          {shown.map((i) => (
            <li key={i.id} className="space-y-1 rounded-md border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">
                  {humanize(i.source_module)} → {humanize(i.target_module)}
                </span>
                <StatusBadge status={i.status} />
              </div>
              <p className="text-xs text-muted-foreground">{i.service}</p>
              {i.accounting_impact && (
                <p className="text-xs">
                  <span className="text-muted-foreground">Accounting: </span>
                  {i.accounting_impact}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// ── Certification checklist ──────────────────────────────────────────────────

export function ChecklistPanel() {
  const { data, isLoading, isError } = useChecklist();
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load the checklist." />;

  const complete = data.checklist.filter((c) => c.status === "COMPLETE").length;
  return (
    <Section
      title="Certification checklist"
      description={`${complete} of ${data.total} modules COMPLETE (evidence-backed)`}
    >
      <ul className="grid gap-2 sm:grid-cols-2">
        {data.checklist.map((c) => (
          <li key={c.id} className="flex items-center gap-2 rounded-md border p-2 text-sm">
            <Badge variant="outline" className="font-mono">
              {c.id}
            </Badge>
            <span className="flex-1">{c.name}</span>
            {c.status ? (
              <StatusBadge status={c.status} />
            ) : (
              <span className="text-xs text-muted-foreground">{c.module}</span>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

// ── Simulation runner ────────────────────────────────────────────────────────

function StepList({ steps }: { steps: SimulationResult["steps"] }) {
  return (
    <ul className="mt-2 space-y-1" aria-label="Simulation steps">
      {steps.map((s, i) => (
        <li key={`${s.name}-${i}`} className="flex items-center gap-2 text-xs">
          <StatusBadge status={s.status} />
          <span className="font-medium">{s.name}</span>
          {s.error && <span className="text-destructive">{s.error}</span>}
        </li>
      ))}
    </ul>
  );
}

export function SimulationRunner() {
  const { data, isLoading, isError } = useScenarios();
  const runOne = useRunScenario();
  const runAll = useRunAllScenarios();
  const [results, setResults] = useState<Record<string, SimulationResult>>({});

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !data) return <ErrorState title="Couldn't load" description="Could not load simulation scenarios." />;

  async function handleRun(key: string) {
    const res = await runOne.mutateAsync(key);
    setResults((prev) => ({ ...prev, [key]: res }));
  }

  async function handleRunAll() {
    const all = await runAll.mutateAsync();
    // refresh each scenario's detailed result so the per-scenario panels update too
    const detailed: Record<string, SimulationResult> = {};
    for (const key of Object.keys(all.scenarios)) {
      detailed[key] = await runOne.mutateAsync(key);
    }
    setResults((prev) => ({ ...prev, ...detailed }));
  }

  return (
    <Section
      title="Business simulations"
      description="End-to-end scenarios executed with real service calls."
      action={
        <Button size="sm" onClick={handleRunAll} disabled={runAll.isPending || runOne.isPending}>
          {runAll.isPending ? "Running…" : "Run all"}
        </Button>
      }
    >
      <ul className="space-y-2">
        {data.scenarios.map((sc) => {
          const result = results[sc.key];
          return (
            <li key={sc.key} className="space-y-1 rounded-md border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-medium">{sc.name}</span>
                  <p className="text-xs text-muted-foreground">{sc.description}</p>
                </div>
                <div className="flex items-center gap-2">
                  {result && (
                    <StatusBadge status={result.passed ? "passed" : "failed"} />
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRun(sc.key)}
                    disabled={runOne.isPending}
                  >
                    Run
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {sc.modules.map((m) => (
                  <Badge key={m} variant="outline" className="text-xs">
                    {m}
                  </Badge>
                ))}
              </div>
              {result && <StepList steps={result.steps} />}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

// ── Console ──────────────────────────────────────────────────────────────────

export function CertificationConsole() {
  return (
    <div className="space-y-6">
      <CertificationOverview />
      <ModuleHealthGrid />
      <ReadinessGrid />
      <ArchitectureValidationPanel />
      <IntegrationRegistryPanel />
      <SimulationRunner />
      <ChecklistPanel />
    </div>
  );
}
