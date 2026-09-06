"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  useAssignAsset,
  useCompleteWorkOrder,
  useEnsureSetup,
  useInspectAsset,
  useRetireAsset,
  useReturnAsset,
  useTransferAsset,
} from "@/lib/assets/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const ASSETS_SLUG = "assets";

/** Asset modules → the generic F1.7 record-list route for each entity, grouped like the backend nav.
 * Every asset entity is reachable from here so no asset area is orphaned. The "Insights" group links
 * to the framework dashboard/report runtimes (asset dashboards + reports are provisioned on install). */
const MODULES: { label: string; entities: { href: string; label: string }[] }[] = [
  {
    label: "Registry",
    entities: [
      { href: "/e/asset", label: "Assets" },
      { href: "/e/asset_category", label: "Categories" },
      { href: "/e/asset_type", label: "Asset types" },
    ],
  },
  {
    label: "Operations",
    entities: [
      { href: "/e/asset_assignment", label: "Assignments" },
      { href: "/e/asset_transfer", label: "Transfers" },
      { href: "/e/asset_request", label: "Requests" },
      { href: "/e/asset_reservation", label: "Reservations" },
    ],
  },
  {
    label: "Maintenance",
    entities: [
      { href: "/e/maintenance_plan", label: "Maintenance plans" },
      { href: "/e/maintenance_work_order", label: "Work orders" },
      { href: "/e/inspection", label: "Inspections" },
    ],
  },
  {
    label: "Records",
    entities: [
      { href: "/e/warranty", label: "Warranties" },
      { href: "/e/asset_contract", label: "Contracts" },
      { href: "/e/asset_inventory_count", label: "Inventory counts" },
    ],
  },
  {
    label: "Insights",
    entities: [
      { href: "/dashboards", label: "Dashboards" },
      { href: "/reports", label: "Reports" },
    ],
  },
];

/** Native-engine sub-pages reached from the overview. */
const ENGINE_LINKS: { href: string; label: string; description: string }[] = [
  {
    href: "/assets/depreciation",
    label: "Depreciation",
    description: "Schedules, immutable period runs, and a no-write preview.",
  },
  {
    href: "/assets/disposals",
    label: "Disposals",
    description: "Sale / scrap / donation / write-off with gain or loss.",
  },
];

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * Asset Management (EAM) overview (Phase P2.9). HYBRID solution: the asset master-data/operational
 * entities are rendered by the generic F1.7 record runtime; this overview ties them together with
 * module-grouped links, the native depreciation/disposal engine sub-pages, and the asset lifecycle
 * actions (assign/return/transfer/inspect/retire, complete work order) the metadata runtime can't
 * express. If the assets solution isn't installed, prompts to install it.
 */
export function AssetsOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === ASSETS_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
      <EngineNav />
      <ModuleNav />
      {canManage && <RunSetup />}
      <LifecycleActions />
    </div>
  );
}

export function NotInstalled() {
  return (
    <div className="space-y-4">
      <EmptyState
        title="Asset Management isn't installed yet"
        description="Install the Assets solution to provision the asset registry, operations, maintenance, and records entities plus the native depreciation and disposal engines."
      />
      <div className="flex flex-wrap justify-center gap-2">
        <Button asChild>
          <Link href="/solutions">Browse solutions</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/solutions/new">Create solution</Link>
        </Button>
      </div>
    </div>
  );
}

function EngineNav() {
  return (
    <section className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Native engines</h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ENGINE_LINKS.map((e) => (
          <li key={e.href}>
            <Link
              href={e.href}
              className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent"
            >
              <span className="text-sm font-medium">{e.label}</span>
              <span className="text-xs text-muted-foreground">{e.description}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ModuleNav() {
  return (
    <div className="space-y-4">
      {MODULES.map((m) => (
        <section key={m.label} className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{m.label}</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {m.entities.map((e) => (
              <li key={e.href}>
                <Link
                  href={e.href}
                  className="flex h-full items-center rounded-lg border p-4 text-sm font-medium transition-colors hover:bg-accent"
                >
                  {e.label}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function RunSetup() {
  const setup = useEnsureSetup();
  async function run() {
    try {
      const res = await setup.mutateAsync();
      toast.success(res.detail || "Asset number sequence ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">Ensure the gapless AST- asset number sequence exists.</p>
      </div>
      <Button onClick={run} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
    </div>
  );
}

export function LifecycleActions() {
  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Lifecycle actions</h2>
        <p className="text-xs text-muted-foreground">
          Advance an asset by its record id. (Deep per-record action buttons inside the generic record
          runtime are out of scope, so the id is entered here as a raw UUID.)
        </p>
      </div>
      <AssignAction />
      <IdAction
        label="Return an asset"
        placeholder="Asset record id"
        actionLabel="Return"
        useAction={useReturnAsset}
        successText="Asset returned"
      />
      <TransferAction />
      <InspectAction />
      <RetireAction />
      <IdAction
        label="Complete a work order"
        placeholder="Work order record id"
        actionLabel="Complete"
        useAction={useCompleteWorkOrder}
        successText="Work order completed"
      />
    </div>
  );
}

/** A lifecycle action driven by a single record id. */
function IdAction({
  label,
  placeholder,
  actionLabel,
  useAction,
  successText,
}: {
  label: string;
  placeholder: string;
  actionLabel: string;
  useAction: () => { mutateAsync: (id: string) => Promise<unknown>; isPending: boolean };
  successText: string;
}) {
  const action = useAction();
  const [id, setId] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await action.mutateAsync(recordId);
      toast.success(successText);
      setId("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : `${label} failed`);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">{label}</span>
        <Input aria-label={label} placeholder={placeholder} value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || action.isPending}>
        {action.isPending ? "Working…" : actionLabel}
      </Button>
    </div>
  );
}

/** Assign an asset to an employee / department / team (any one ref). */
export function AssignAction() {
  const assign = useAssignAsset();
  const [id, setId] = useState("");
  const [employee, setEmployee] = useState("");

  async function run() {
    const recordId = id.trim();
    const ref = employee.trim();
    if (!recordId || !ref) return;
    try {
      await assign.mutateAsync({ recordId, data: { employee: ref } });
      toast.success("Asset assigned");
      setId("");
      setEmployee("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Assign failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Assign an asset</span>
        <Input aria-label="Assign an asset" placeholder="Asset record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Employee</span>
        <Input
          aria-label="Assign an asset employee"
          placeholder="Employee record id"
          value={employee}
          onChange={(e) => setEmployee(e.target.value)}
        />
      </label>
      <Button onClick={run} disabled={!id.trim() || !employee.trim() || assign.isPending}>
        {assign.isPending ? "Working…" : "Assign"}
      </Button>
    </div>
  );
}

/** Transfer an asset between locations / holders. */
export function TransferAction() {
  const transfer = useTransferAsset();
  const [id, setId] = useState("");
  const [transferType, setTransferType] = useState("location");
  const [fromRef, setFromRef] = useState("");
  const [toRef, setToRef] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId || !fromRef.trim() || !toRef.trim()) return;
    try {
      await transfer.mutateAsync({
        recordId,
        data: { transfer_type: transferType, from_ref: fromRef.trim(), to_ref: toRef.trim() },
      });
      toast.success("Asset transferred");
      setId("");
      setFromRef("");
      setToRef("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Transfer failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Transfer an asset</span>
        <Input aria-label="Transfer an asset" placeholder="Asset record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="w-40 space-y-1">
        <span className="text-xs font-medium">Type</span>
        <Select value={transferType} onValueChange={setTransferType}>
          <SelectTrigger aria-label="Transfer type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="location">Location</SelectItem>
            <SelectItem value="custodian">Custodian</SelectItem>
            <SelectItem value="department">Department</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">From</span>
        <Input aria-label="Transfer from" placeholder="From ref" value={fromRef} onChange={(e) => setFromRef(e.target.value)} />
      </label>
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">To</span>
        <Input aria-label="Transfer to" placeholder="To ref" value={toRef} onChange={(e) => setToRef(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || !fromRef.trim() || !toRef.trim() || transfer.isPending}>
        {transfer.isPending ? "Working…" : "Transfer"}
      </Button>
    </div>
  );
}

/** Record an inspection result against an asset. */
export function InspectAction() {
  const inspect = useInspectAsset();
  const [id, setId] = useState("");
  const [result, setResult] = useState<"passed" | "failed" | "requires_attention">("passed");
  const [notes, setNotes] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await inspect.mutateAsync({ recordId, data: { result, notes: notes.trim() } });
      toast.success("Inspection recorded");
      setId("");
      setNotes("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Inspect failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Inspect an asset</span>
        <Input aria-label="Inspect an asset" placeholder="Asset record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="w-48 space-y-1">
        <span className="text-xs font-medium">Result</span>
        <Select value={result} onValueChange={(v) => setResult(v as typeof result)}>
          <SelectTrigger aria-label="Inspection result">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="passed">Passed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="requires_attention">Requires attention</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Notes</span>
        <Input aria-label="Inspection notes" placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || inspect.isPending}>
        {inspect.isPending ? "Working…" : "Inspect"}
      </Button>
    </div>
  );
}

/** Retire an asset (admin-gated by the API) — produces a disposal/retirement record. */
export function RetireAction() {
  const retire = useRetireAsset();
  const [id, setId] = useState("");
  const [reason, setReason] = useState("");
  const [residual, setResidual] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId || !reason.trim()) return;
    try {
      await retire.mutateAsync({
        recordId,
        data: { reason: reason.trim(), residual_value: residual.trim() || "0" },
      });
      toast.success("Asset retired");
      setId("");
      setReason("");
      setResidual("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Retire failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Retire an asset</span>
        <Input aria-label="Retire an asset" placeholder="Asset record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Reason</span>
        <Input aria-label="Retire reason" placeholder="End of life" value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <label className="w-40 space-y-1">
        <span className="text-xs font-medium">Residual value</span>
        <Input aria-label="Residual value" placeholder="0" inputMode="decimal" value={residual} onChange={(e) => setResidual(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || !reason.trim() || retire.isPending}>
        {retire.isPending ? "Working…" : "Retire"}
      </Button>
    </div>
  );
}

export { ASSETS_SLUG, MODULES, ENGINE_LINKS };
