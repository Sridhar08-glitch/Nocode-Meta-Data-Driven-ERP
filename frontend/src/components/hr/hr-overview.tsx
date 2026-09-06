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
  useAcceptOffer,
  useApproveLeave,
  useCompleteInterview,
  useCompletePerformance,
  useEnsureSetup,
  useHireCandidate,
  useOffboardEmployee,
  usePromoteEmployee,
  useRejectLeave,
  useTransferEmployee,
} from "@/lib/hr/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const HR_SLUG = "hr";

/** HR modules → the generic F1.7 record-list route for each entity, grouped like the backend nav.
 * Every HR entity is reachable from here so no HR area is orphaned. The "Insights" group links to
 * the framework dashboard/report runtimes (the HR dashboards + reports are provisioned on install).
 */
const MODULES: { label: string; entities: { href: string; label: string }[] }[] = [
  {
    label: "Organization",
    entities: [
      { href: "/e/branch", label: "Branches" },
      { href: "/e/division", label: "Divisions" },
      { href: "/e/department", label: "Departments" },
      { href: "/e/team", label: "Teams" },
      { href: "/e/position", label: "Positions" },
      { href: "/e/job_family", label: "Job families" },
      { href: "/e/job_grade", label: "Job grades" },
    ],
  },
  {
    label: "Recruitment",
    entities: [
      { href: "/e/candidate", label: "Candidates" },
      { href: "/e/interview", label: "Interviews" },
      { href: "/e/offer", label: "Offers" },
    ],
  },
  {
    label: "People",
    entities: [
      { href: "/e/employee", label: "Employees" },
      { href: "/e/onboarding_plan", label: "Onboarding plans" },
      { href: "/e/onboarding_task", label: "Onboarding tasks" },
    ],
  },
  {
    label: "Time",
    entities: [
      { href: "/e/attendance_record", label: "Attendance" },
      { href: "/e/shift", label: "Shifts" },
      { href: "/e/leave_request", label: "Leave requests" },
      { href: "/e/leave_type", label: "Leave types" },
      { href: "/e/leave_balance", label: "Leave balances" },
      { href: "/e/holiday_calendar", label: "Holidays" },
    ],
  },
  {
    label: "Performance",
    entities: [
      { href: "/e/review_cycle", label: "Review cycles" },
      { href: "/e/goal", label: "Goals" },
      { href: "/e/kpi", label: "KPIs" },
      { href: "/e/performance_review", label: "Performance reviews" },
    ],
  },
  {
    label: "Lifecycle",
    entities: [
      { href: "/e/promotion", label: "Promotions" },
      { href: "/e/transfer", label: "Transfers" },
      { href: "/e/exit_request", label: "Exit requests" },
      { href: "/e/asset_return", label: "Asset returns" },
      { href: "/e/clearance", label: "Clearances" },
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

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * HR Solution overview (Phase P2.7). Ties the HR lifecycle together: module-grouped links to the
 * generic entity screens + the native lifecycle actions (setup, hire candidate, complete interview,
 * accept offer, approve/reject leave, complete review, promote/transfer/offboard employee) the
 * metadata runtime can't express. If the HR solution isn't installed, prompts to install it.
 */
export function HrOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === HR_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
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
        title="HR isn't installed yet"
        description="Install the HR solution to provision the org structure, recruitment, people, time, performance, and lifecycle entities."
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
      toast.success(res.detail || "HR number sequences ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">
          Ensure gapless candidate / interview / offer / employee number sequences exist.
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
          Advance an HR document by its record id. (Deep per-record action buttons inside the generic
          record runtime are out of scope, so the id is entered here.)
        </p>
      </div>
      <IdAction
        label="Hire a candidate"
        placeholder="Candidate record id"
        actionLabel="Hire"
        useAction={useHireCandidate}
        successText="Candidate hired — employee created"
      />
      <IdAction
        label="Complete an interview"
        placeholder="Interview record id"
        actionLabel="Complete"
        useAction={useCompleteInterview}
        successText="Interview completed"
      />
      <IdAction
        label="Accept an offer"
        placeholder="Offer record id"
        actionLabel="Accept"
        useAction={useAcceptOffer}
        successText="Offer accepted"
      />
      <IdAction
        label="Approve a leave request"
        placeholder="Leave request record id"
        actionLabel="Approve"
        useAction={useApproveLeave}
        successText="Leave approved"
      />
      <IdAction
        label="Reject a leave request"
        placeholder="Leave request record id"
        actionLabel="Reject"
        useAction={useRejectLeave}
        successText="Leave rejected"
      />
      <IdAction
        label="Complete a performance review"
        placeholder="Performance review record id"
        actionLabel="Complete"
        useAction={useCompletePerformance}
        successText="Performance review completed"
      />
      <FieldAction
        label="Promote an employee"
        placeholder="Employee record id"
        fieldLabel="New position"
        fieldPlaceholder="Position record id"
        actionLabel="Promote"
        useAction={usePromoteEmployee}
        toVars={(recordId, value) => ({ recordId, newPosition: value })}
        successText="Employee promoted"
      />
      <FieldAction
        label="Transfer an employee"
        placeholder="Employee record id"
        fieldLabel="New department"
        fieldPlaceholder="Department record id"
        actionLabel="Transfer"
        useAction={useTransferEmployee}
        toVars={(recordId, value) => ({ recordId, newDepartment: value })}
        successText="Employee transferred"
      />
      <IdAction
        label="Offboard an employee"
        placeholder="Employee record id"
        actionLabel="Offboard"
        useAction={useOffboardEmployee}
        successText="Employee offboarded"
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

/** A lifecycle action driven by a record id + a second field value (e.g. promote/transfer target). */
function FieldAction<V>({
  label,
  placeholder,
  fieldLabel,
  fieldPlaceholder,
  actionLabel,
  useAction,
  toVars,
  successText,
}: {
  label: string;
  placeholder: string;
  fieldLabel: string;
  fieldPlaceholder: string;
  actionLabel: string;
  useAction: () => { mutateAsync: (vars: V) => Promise<unknown>; isPending: boolean };
  toVars: (recordId: string, value: string) => V;
  successText: string;
}) {
  const action = useAction();
  const [id, setId] = useState("");
  const [value, setValue] = useState("");

  async function run() {
    const recordId = id.trim();
    const fieldValue = value.trim();
    if (!recordId || !fieldValue) return;
    try {
      await action.mutateAsync(toVars(recordId, fieldValue));
      toast.success(successText);
      setId("");
      setValue("");
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
        <span className="text-xs font-medium">{fieldLabel}</span>
        <Input
          aria-label={`${label} ${fieldLabel.toLowerCase()}`}
          placeholder={fieldPlaceholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>
      <Button onClick={run} disabled={!id.trim() || !value.trim() || action.isPending}>
        {action.isPending ? "Working…" : actionLabel}
      </Button>
    </div>
  );
}

export { HR_SLUG, MODULES };
