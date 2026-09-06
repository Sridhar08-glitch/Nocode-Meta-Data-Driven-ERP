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
import type { ProjectEntitySlug } from "@/lib/projects/api";
import {
  useApproveBudget,
  useApproveChangeRequest,
  useApproveDeliverable,
  useApproveExpense,
  useApproveTimesheet,
  useBaselineProject,
  useCompleteMilestone,
  useCompleteProject,
  useCompleteTask,
  useCreateDocument,
  useEnsureSetup,
  useStartProject,
} from "@/lib/projects/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const PROJECTS_SLUG = "projects";

/** Project modules → the generic F1.7 record-list route for each entity, grouped like the backend nav.
 * Every project entity is reachable from here so no project area is orphaned. The "Insights" group
 * links to the framework dashboard/report runtimes (project dashboards + reports are provisioned on
 * install). */
const MODULES: { label: string; entities: { href: string; label: string }[] }[] = [
  {
    label: "Delivery",
    entities: [
      { href: "/e/portfolio", label: "Portfolios" },
      { href: "/e/program", label: "Programs" },
      { href: "/e/project", label: "Projects" },
    ],
  },
  {
    label: "Work",
    entities: [
      { href: "/e/task", label: "Tasks" },
      { href: "/e/milestone", label: "Milestones" },
      { href: "/e/deliverable", label: "Deliverables" },
      { href: "/e/sprint", label: "Sprints" },
      { href: "/e/task_dependency", label: "Dependencies" },
    ],
  },
  {
    label: "People",
    entities: [
      { href: "/e/project_member", label: "Project members" },
      { href: "/e/employee_skill", label: "Skills" },
      { href: "/e/timesheet", label: "Timesheets" },
      { href: "/e/expense", label: "Expenses" },
    ],
  },
  {
    label: "Governance",
    entities: [
      { href: "/e/risk", label: "Risks" },
      { href: "/e/issue", label: "Issues" },
      { href: "/e/change_request", label: "Change requests" },
      { href: "/e/quality_review", label: "Quality reviews" },
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
    href: "/projects/financials",
    label: "Financials",
    description: "Budget, profitability, and earned-value (EVM) for a project, plus cost rollup.",
  },
  {
    href: "/projects/schedule",
    label: "Schedule",
    description: "Critical path, total float, and a gantt view computed server-side.",
  },
  {
    href: "/projects/resources",
    label: "Resources",
    description: "Utilization, allocation conflicts, and weekly capacity across employees.",
  },
];

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * Project Management + PSA overview (Phase P2.10). HYBRID solution: the project document entities are
 * rendered by the generic F1.7 record runtime; this overview ties them together with module-grouped
 * links, the native financials/schedule/resources engine sub-pages, and the project lifecycle actions
 * (start/complete/baseline, approve budget, complete task/milestone, approve timesheet/expense/
 * change-request/deliverable) the metadata runtime can't express. If the projects solution isn't
 * installed, prompts to install it.
 */
export function ProjectsOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === PROJECTS_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
      <EngineNav />
      <ModuleNav />
      {canManage && <RunSetup />}
      <CreateProject />
      <LifecycleActions />
    </div>
  );
}

export function NotInstalled() {
  return (
    <div className="space-y-4">
      <EmptyState
        title="Project Management isn't installed yet"
        description="Install the Projects solution to provision the portfolio/program/project delivery, work, people, and governance entities plus the native cost-rollup, financials (EVM), scheduling, and resourcing engines."
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
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
      toast.success(res.detail || "Project number sequences ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">Ensure the gapless PRJ- / TSK- number sequences exist.</p>
      </div>
      <Button onClick={run} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
    </div>
  );
}

/** Quick-create a numbered project or task document (the full create lives in the generic runtime). */
export function CreateProject() {
  const create = useCreateDocument();
  const [entitySlug, setEntitySlug] = useState<ProjectEntitySlug>("project");
  const [name, setName] = useState("");

  async function run() {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      const res = await create.mutateAsync({ entitySlug, data: { name: trimmed } });
      toast.success(res.number ? `Created ${res.number}` : "Document created");
      setName("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Quick create</h2>
        <p className="text-xs text-muted-foreground">
          Create a numbered project or task; richer fields are available in the generic record runtime.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-40 space-y-1">
          <span className="text-xs font-medium">Type</span>
          <Select value={entitySlug} onValueChange={(v) => setEntitySlug(v as ProjectEntitySlug)}>
            <SelectTrigger aria-label="Document type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="project">Project</SelectItem>
              <SelectItem value="task">Task</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <label className="flex-1 space-y-1">
          <span className="text-xs font-medium">Name</span>
          <Input
            aria-label="Document name"
            placeholder="Website rebuild"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <Button onClick={run} disabled={!name.trim() || create.isPending}>
          {create.isPending ? "Creating…" : "Create"}
        </Button>
      </div>
    </div>
  );
}

export function LifecycleActions() {
  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Lifecycle actions</h2>
        <p className="text-xs text-muted-foreground">
          Advance a project document by its record id. (Deep per-record action buttons inside the generic
          record runtime are out of scope, so the id is entered here as a raw UUID.)
        </p>
      </div>
      <IdAction label="Start a project" placeholder="Project record id" actionLabel="Start" useAction={useStartProject} successText="Project started" />
      <IdAction label="Complete a project" placeholder="Project record id" actionLabel="Complete" useAction={useCompleteProject} successText="Project completed" />
      <IdAction label="Baseline a project" placeholder="Project record id" actionLabel="Baseline" useAction={useBaselineProject} successText="Baseline captured" />
      <IdAction label="Approve a budget" placeholder="Project record id" actionLabel="Approve" useAction={useApproveBudget} successText="Budget approved" />
      <IdAction label="Complete a task" placeholder="Task record id" actionLabel="Complete" useAction={useCompleteTask} successText="Task completed" />
      <IdAction label="Complete a milestone" placeholder="Milestone record id" actionLabel="Complete" useAction={useCompleteMilestone} successText="Milestone completed" />
      <IdAction label="Approve a timesheet" placeholder="Timesheet record id" actionLabel="Approve" useAction={useApproveTimesheet} successText="Timesheet approved" />
      <IdAction label="Approve an expense" placeholder="Expense record id" actionLabel="Approve" useAction={useApproveExpense} successText="Expense approved" />
      <IdAction label="Approve a change request" placeholder="Change request record id" actionLabel="Approve" useAction={useApproveChangeRequest} successText="Change request approved" />
      <IdAction label="Approve a deliverable" placeholder="Deliverable record id" actionLabel="Approve" useAction={useApproveDeliverable} successText="Deliverable approved" />
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

export { PROJECTS_SLUG, MODULES, ENGINE_LINKS };
