"use client";

import { ArrowRight } from "lucide-react";
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
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type {
  DryRunResult,
  Environment,
  ObjectRef,
  PromotionPackage,
} from "@/lib/environments/api";
import {
  useApprovePackage,
  useCreatePackage,
  useEnsureEnvironments,
  useEnvironments,
  useExecutePackage,
  usePackage,
  usePackages,
  usePromotionDashboard,
  useRollbackPackage,
} from "@/lib/environments/hooks";

import { DiffSummary, RiskSummaryBadges, shortHash, StatusBadge } from "./shared";

const APPROVAL_ROLES = ["reviewer", "approver", "release_manager"] as const;

function errMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function Section({
  title,
  description,
  children,
  action,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
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

/** DEV→TEST→UAT→PROD strip with branch names + provision button. */
export function EnvironmentsStrip({ isAdmin }: { isAdmin: boolean }) {
  const q = useEnvironments();
  const ensure = useEnsureEnvironments();
  const envs = (q.data ?? []).slice().sort((a, b) => a.sequence - b.sequence);

  async function provision() {
    try {
      await ensure.mutateAsync();
      toast.success("Environments provisioned");
    } catch (err) {
      toast.error(errMessage(err, "Couldn't provision environments"));
    }
  }

  return (
    <Section
      title="Environments"
      description="Config promotes left to right; PROD is the protected production environment."
      action={
        isAdmin ? (
          <Button size="sm" variant="outline" onClick={provision} disabled={ensure.isPending}>
            {ensure.isPending ? "Setting up…" : "Set up environments"}
          </Button>
        ) : null
      }
    >
      {q.isLoading ? (
        <Skeleton className="h-20 w-full" />
      ) : q.isError ? (
        <ErrorState title="Couldn't load environments" />
      ) : envs.length === 0 ? (
        <EmptyState
          title="No environments yet"
          description={isAdmin ? "Provision the DEV→TEST→UAT→PROD chain to begin." : "Ask an admin to set up environments."}
        />
      ) : (
        <ol className="flex flex-wrap items-center gap-2">
          {envs.map((e, i) => (
            <li key={e.id} className="flex items-center gap-2">
              <div className="rounded-md border p-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium uppercase">{e.name}</span>
                  {e.is_production && <Badge variant="warning">prod</Badge>}
                </div>
                <code className="text-xs text-muted-foreground">{e.branch}</code>
              </div>
              {i < envs.length - 1 && (
                <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
              )}
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

/** Promotion KPIs: success rate, pending/approved/rollbacks, risk distribution, velocity. */
export function PromotionDashboardCard() {
  const q = usePromotionDashboard();
  if (q.isLoading) return <Skeleton className="h-32 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't load the promotion dashboard" />;
  const d = q.data!;
  const pct = Math.round((d.success_rate ?? 0) * 100);
  const kpis: [string, number | string][] = [
    ["Success rate", `${pct}%`],
    ["Pending", d.pending],
    ["Approved", d.approved],
    ["Rollbacks", d.rollbacks],
    ["Release velocity", d.release_velocity],
  ];
  return (
    <Section title="Release dashboard" description="Promotion health across this workspace.">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {kpis.map(([label, n]) => (
          <div key={label} className="rounded-md border p-3">
            <div className="text-2xl font-semibold">{n}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>
      <div className="space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Risk distribution
        </h3>
        <RiskSummaryBadges risk={d.risk_distribution} />
      </div>
    </Section>
  );
}

function EnvSelect({
  id,
  label,
  value,
  onChange,
  envs,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  envs: Environment[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger id={id} aria-label={label} className="w-48">
          <SelectValue placeholder="Select environment" />
        </SelectTrigger>
        <SelectContent>
          {envs.map((e) => (
            <SelectItem key={e.id} value={e.id}>
              {e.name.toUpperCase()} ({e.branch})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Create a promotion package: source/target/name + optional object rows → diff + risk. */
export function CreatePackageForm() {
  const envQ = useEnvironments();
  const create = useCreatePackage();
  const envs = (envQ.data ?? []).slice().sort((a, b) => a.sequence - b.sequence);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [objects, setObjects] = useState<ObjectRef[]>([]);
  const [result, setResult] = useState<PromotionPackage | null>(null);

  function setObj(i: number, patch: Partial<ObjectRef>) {
    setObjects((os) => os.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  }

  const valid = !!source && !!target && source !== target && !!name.trim();

  async function submit() {
    if (!valid) return;
    try {
      const pkg = await create.mutateAsync({
        source_env_id: source,
        target_env_id: target,
        name: name.trim(),
        objects: objects.filter((o) => o.object_type && o.object_id),
      });
      setResult(pkg);
      toast.success("Promotion package created");
    } catch (err) {
      toast.error(errMessage(err, "Couldn't create the package"));
    }
  }

  return (
    <Section
      title="Create promotion package"
      description="Bundle config objects to promote. Object refs are raw UUIDs (no picker yet); leave empty to let the precheck pick up the full diff."
    >
      <div className="flex flex-wrap items-end gap-3">
        <EnvSelect id="cp-source" label="Source" value={source} onChange={setSource} envs={envs} />
        <EnvSelect id="cp-target" label="Target" value={target} onChange={setTarget} envs={envs} />
        <div className="space-y-1.5">
          <Label htmlFor="cp-name">Package name</Label>
          <Input
            id="cp-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Release 2026.06"
            className="w-56"
          />
        </div>
      </div>

      {source && target && source === target && (
        <p className="text-sm text-destructive" role="alert">
          Source and target must differ.
        </p>
      )}

      <div className="space-y-2">
        <Label>Objects (optional)</Label>
        <ul className="space-y-2">
          {objects.map((o, i) => (
            <li key={i} className="flex flex-wrap items-end gap-2">
              <Input
                aria-label={`Object ${i + 1} type`}
                value={o.object_type}
                onChange={(e) => setObj(i, { object_type: e.target.value })}
                placeholder="entity / field / report…"
                className="w-48"
              />
              <Input
                aria-label={`Object ${i + 1} id`}
                value={o.object_id}
                onChange={(e) => setObj(i, { object_id: e.target.value })}
                placeholder="uuid"
                className="w-56"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setObjects((os) => os.filter((_, j) => j !== i))}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setObjects((os) => [...os, { object_type: "", object_id: "" }])}
        >
          Add object
        </Button>
      </div>

      <Button onClick={submit} disabled={!valid || create.isPending}>
        {create.isPending ? "Creating…" : "Create package"}
      </Button>

      {result && (
        <div className="space-y-3 rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{result.name}</span>
            <StatusBadge status={result.status} />
            <RiskSummaryBadges risk={result.risk_summary} />
            {(result.risk_summary.blocked ?? 0) > 0 && (
              <Badge variant="destructive">precheck blocked</Badge>
            )}
            <code className="text-xs text-muted-foreground">{shortHash(result.package_hash)}</code>
          </div>
          <DiffSummary diff={result.diff} />
        </div>
      )}
    </Section>
  );
}

/** Packages table; clicking a row selects it for the detail panel. */
export function PackagesList({
  envs,
  selectedId,
  onSelect,
}: {
  envs: Environment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const q = usePackages();
  const byId = new Map(envs.map((e) => [e.id, e]));
  const envName = (id: string) => byId.get(id)?.name.toUpperCase() ?? id.slice(0, 8);
  const rows = q.data ?? [];

  if (q.isLoading) return <Skeleton className="h-32 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't load packages" />;
  if (rows.length === 0) {
    return <EmptyState title="No packages yet" description="Create a promotion package above." />;
  }
  return (
    <ul className="space-y-2">
      {rows.map((p) => (
        <li key={p.id}>
          <button
            onClick={() => onSelect(p.id)}
            aria-label={`Package ${p.name}`}
            className={`flex w-full flex-wrap items-center gap-3 rounded-md border p-3 text-left text-sm transition-colors hover:bg-accent ${
              selectedId === p.id ? "ring-2 ring-ring" : ""
            }`}
          >
            <span className="font-medium">{p.name}</span>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              {envName(p.source_env_id)} <ArrowRight className="size-3" aria-hidden /> {envName(p.target_env_id)}
            </span>
            <StatusBadge status={p.status} />
            <RiskSummaryBadges risk={p.risk_summary} />
            <code className="ml-auto text-xs text-muted-foreground">{shortHash(p.package_hash)}</code>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Package detail: diff + risk + approvals + lifecycle actions (admin-gated, status-aware). */
export function PackageDetail({ id, isAdmin }: { id: string; isAdmin: boolean }) {
  const q = usePackage(id);
  const approve = useApprovePackage(id);
  const execute = useExecutePackage(id);
  const rollback = useRollbackPackage(id);
  const [role, setRole] = useState<string>("reviewer");
  const [dryRun, setDryRun] = useState<DryRunResult | null>(null);

  if (q.isLoading) return <Skeleton className="h-48 w-full" />;
  if (q.isError) return <ErrorState title="Couldn't load the package" />;
  const p = q.data!;

  async function doApprove() {
    setDryRun(null);
    try {
      await approve.mutateAsync(role);
      toast.success(`Approved as ${role.replace("_", " ")}`);
    } catch (err) {
      toast.error(errMessage(err, "Approval failed"));
    }
  }
  async function doExecute(asDryRun: boolean) {
    try {
      const res = await execute.mutateAsync(asDryRun);
      if ("dry_run" in res) {
        setDryRun(res);
        toast.success(res.would_merge ? "Dry-run: would merge cleanly" : "Dry-run: merge conflicts");
      } else {
        setDryRun(null);
        if (res.status === "executed") toast.success("Promoted");
        else toast.error("Promotion failed (conflicts)");
      }
    } catch (err) {
      toast.error(errMessage(err, asDryRun ? "Dry-run failed" : "Promotion failed"));
    }
  }
  async function doRollback() {
    setDryRun(null);
    try {
      await rollback.mutateAsync();
      toast.success("Rolled back");
    } catch (err) {
      toast.error(errMessage(err, "Rollback failed"));
    }
  }

  const canApprove = isAdmin && (p.status === "precheck" || p.status === "draft");
  const canExecute = isAdmin && p.status === "approved";
  const canRollback = isAdmin && p.status === "executed";

  return (
    <Section
      title={p.name}
      description={`version ${p.version} · ${p.status.replace("_", " ")} · ${shortHash(p.package_hash)}`}
      action={<StatusBadge status={p.status} />}
    >
      <div className="space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Risk</h3>
        <RiskSummaryBadges risk={p.risk_summary} />
      </div>

      <div className="space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Diff</h3>
        <DiffSummary diff={p.diff} />
      </div>

      <div className="space-y-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Approvals
        </h3>
        {(p.approvals ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No approvals yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {p.approvals!.map((a, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
                <Badge variant="outline">{a.role.replace("_", " ")}</Badge>
                <Badge variant={a.decision === "approved" ? "success" : "secondary"}>{a.decision}</Badge>
                <span className="text-xs text-muted-foreground">{a.approver_id ?? "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {isAdmin && (
        <div className="space-y-3 border-t pt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Lifecycle
          </h3>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="pkg-role">Approve as</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger id="pkg-role" aria-label="Approve as" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {APPROVAL_ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={doApprove} disabled={!canApprove || approve.isPending}>
              {approve.isPending ? "Approving…" : "Approve"}
            </Button>
            <Button
              variant="outline"
              onClick={() => doExecute(true)}
              disabled={!canExecute || execute.isPending}
            >
              Dry-run
            </Button>
            <Button onClick={() => doExecute(false)} disabled={!canExecute || execute.isPending}>
              {execute.isPending ? "Promoting…" : "Promote"}
            </Button>
            <Button variant="destructive" onClick={doRollback} disabled={!canRollback || rollback.isPending}>
              {rollback.isPending ? "Rolling back…" : "Rollback"}
            </Button>
          </div>

          {dryRun && (
            <div className="space-y-2 rounded-md border p-3" aria-label="Dry-run result">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={dryRun.would_merge ? "success" : "destructive"}>
                  {dryRun.would_merge ? "Would merge cleanly" : "Would conflict"}
                </Badge>
                <RiskSummaryBadges risk={dryRun.risk} />
                <code className="text-xs text-muted-foreground">
                  base {shortHash(dryRun.target_sha_before)}
                </code>
              </div>
              <DiffSummary diff={dryRun.diff} />
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

/** Release console (Phase P2.15) — environments, dashboard, create + manage promotion packages. */
export function ReleaseConsole({ isAdmin }: { isAdmin: boolean }) {
  const envQ = useEnvironments();
  const envs = envQ.data ?? [];
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <EnvironmentsStrip isAdmin={isAdmin} />
      {/* The dashboard endpoint is admin-only on the backend. */}
      {isAdmin && <PromotionDashboardCard />}
      {isAdmin && <CreatePackageForm />}
      <Section title="Promotion packages" description="Select a package to view its diff and lifecycle.">
        <PackagesList envs={envs} selectedId={selected} onSelect={setSelected} />
      </Section>
      {selected && <PackageDetail id={selected} isAdmin={isAdmin} />}
    </div>
  );
}
