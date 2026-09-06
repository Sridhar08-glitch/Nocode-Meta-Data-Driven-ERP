"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  useCompleteActivity,
  useEnsureSetup,
  useLoseOpportunity,
  useQualifyLead,
  useWinOpportunity,
} from "@/lib/crm/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const CRM_SLUG = "crm";

/** CRM pipeline stages → the generic F1.7 record-list route for each entity. */
const STAGES: { href: string; label: string; description: string }[] = [
  { href: "/e/lead", label: "Leads", description: "Inbound prospects — qualify to start an opportunity." },
  { href: "/e/account", label: "Accounts", description: "Companies you do business with." },
  { href: "/e/contact", label: "Contacts", description: "People at your accounts." },
  { href: "/e/opportunity", label: "Opportunities", description: "Open deals — win or lose to close." },
  { href: "/e/activity", label: "Activities", description: "Calls, meetings, and tasks — complete to log." },
];

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * CRM Solution overview (Phase P2.6). Ties the CRM pipeline together: links to the generic entity
 * screens + the native lifecycle actions (setup, qualify lead, win/lose opportunity, complete activity)
 * the metadata runtime can't express. If the CRM solution isn't installed, prompts to install it.
 */
export function CrmOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === CRM_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
      <LifecycleStages />
      {canManage && <RunSetup />}
      <LifecycleActions />
    </div>
  );
}

export function NotInstalled() {
  return (
    <div className="space-y-4">
      <EmptyState
        title="CRM isn't installed yet"
        description="Install the CRM solution to provision leads, accounts, contacts, opportunities, and activities."
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

function LifecycleStages() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {STAGES.map((s) => (
        <li key={s.href}>
          <Link
            href={s.href}
            className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent"
          >
            <span className="font-medium">{s.label}</span>
            <span className="text-xs text-muted-foreground">{s.description}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function RunSetup() {
  const setup = useEnsureSetup();
  async function run() {
    try {
      const res = await setup.mutateAsync();
      toast.success(res.detail || "CRM number sequences ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">
          Ensure gapless lead / account / opportunity number sequences exist.
        </p>
      </div>
      <Button onClick={run} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
    </div>
  );
}

export function LifecycleActions() {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Lifecycle actions</h2>
        <p className="text-xs text-muted-foreground">
          Advance a CRM document by its record id. (Deep per-record action buttons inside the generic
          record runtime are out of scope, so the id is entered here.)
        </p>
      </div>
      <IdAction
        label="Qualify a lead"
        placeholder="Lead record id"
        actionLabel="Qualify"
        useAction={useQualifyLead}
        successText="Lead qualified — opportunity created"
      />
      <ReasonAction
        label="Win an opportunity"
        placeholder="Opportunity record id"
        actionLabel="Win"
        useAction={useWinOpportunity}
        successText="Opportunity marked won"
      />
      <ReasonAction
        label="Lose an opportunity"
        placeholder="Opportunity record id"
        actionLabel="Lose"
        useAction={useLoseOpportunity}
        successText="Opportunity marked lost"
      />
      <IdAction
        label="Complete an activity"
        placeholder="Activity record id"
        actionLabel="Complete"
        useAction={useCompleteActivity}
        successText="Activity completed"
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

/** A lifecycle action driven by a record id + a close reason. */
function ReasonAction({
  label,
  placeholder,
  actionLabel,
  useAction,
  successText,
}: {
  label: string;
  placeholder: string;
  actionLabel: string;
  useAction: () => {
    mutateAsync: (vars: { recordId: string; reason: string }) => Promise<unknown>;
    isPending: boolean;
  };
  successText: string;
}) {
  const action = useAction();
  const [id, setId] = useState("");
  const [reason, setReason] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await action.mutateAsync({ recordId, reason: reason.trim() });
      toast.success(successText);
      setId("");
      setReason("");
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
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Reason</span>
        <Input
          aria-label={`${label} reason`}
          placeholder="Close reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <Button onClick={run} disabled={!id.trim() || action.isPending}>
        {action.isPending ? "Working…" : actionLabel}
      </Button>
    </div>
  );
}

export { CRM_SLUG, STAGES };
