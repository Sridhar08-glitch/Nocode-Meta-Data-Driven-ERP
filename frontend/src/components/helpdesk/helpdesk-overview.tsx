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
import type { AutoAssignMethod } from "@/lib/helpdesk/api";
import {
  useApproveChange,
  useAssignTicket,
  useAutoAssignTicket,
  useCloseTicket,
  useCreateDocument,
  useEnsureSetup,
  useEscalateTicket,
  useResolveTicket,
  useSetTicketStatus,
  useSubmitCsat,
} from "@/lib/helpdesk/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const HELPDESK_SLUG = "helpdesk";

/** Helpdesk modules → the generic F1.7 record-list route for each entity, grouped like the backend nav.
 * Every helpdesk entity is reachable from here so no helpdesk area is orphaned. The "Insights" group
 * links to the framework dashboard/report runtimes (helpdesk dashboards + reports are provisioned on
 * install). */
const MODULES: { label: string; entities: { href: string; label: string }[] }[] = [
  {
    label: "Service Desk",
    entities: [
      { href: "/e/ticket", label: "Tickets" },
      { href: "/e/ticket_category", label: "Categories" },
      { href: "/e/ticket_task", label: "Ticket tasks" },
    ],
  },
  {
    label: "ITSM",
    entities: [
      { href: "/e/problem", label: "Problems" },
      { href: "/e/itsm_change", label: "Changes" },
      { href: "/e/major_incident", label: "Major incidents" },
    ],
  },
  {
    label: "Knowledge",
    entities: [{ href: "/e/kb_article", label: "Knowledge base" }],
  },
  {
    label: "Customers",
    entities: [
      { href: "/e/service_contract", label: "Service contracts" },
      { href: "/e/ticket_csat", label: "CSAT responses" },
    ],
  },
  {
    label: "Field & Agents",
    entities: [
      { href: "/e/field_service_visit", label: "Field service visits" },
      { href: "/e/agent_profile", label: "Agent profiles" },
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
    href: "/helpdesk/knowledge",
    label: "Knowledge recommendation",
    description: "Deterministic keyword/category article matching for a ticket (no AI).",
  },
  {
    href: "/helpdesk/sla",
    label: "SLA dashboard",
    description: "Breached, warning, on-track, met, and paused SLAs across the workspace.",
  },
];

const TICKET_STATUSES = [
  "new",
  "assigned",
  "in_progress",
  "waiting_customer",
  "waiting_vendor",
  "on_hold",
  "resolved",
  "closed",
] as const;

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * Helpdesk + ITSM overview (Phase P2.11). HYBRID solution: the helpdesk document entities are rendered
 * by the generic F1.7 record runtime; this overview ties them together with module-grouped links, the
 * native knowledge-recommendation + SLA-dashboard engine sub-pages, and the ticket lifecycle actions
 * (assign / auto-assign / escalate / set status / resolve / close / CSAT, approve change) the metadata
 * runtime can't express. If the helpdesk solution isn't installed, prompts to install it.
 */
export function HelpdeskOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === HELPDESK_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
      <EngineNav />
      <ModuleNav />
      {canManage && <RunSetup />}
      <CreateTicket />
      <LifecycleActions />
    </div>
  );
}

export function NotInstalled() {
  return (
    <div className="space-y-4">
      <EmptyState
        title="Helpdesk isn't installed yet"
        description="Install the Helpdesk solution to provision the service-desk, ITSM, knowledge, customer, and field/agent entities plus the native ticket lifecycle, auto-assignment, escalation, knowledge recommendation, CSAT, and SLA engines."
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
      toast.success(res.detail || "Ticket number sequence ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">Ensure the gapless TKT- ticket number sequence exists.</p>
      </div>
      <Button onClick={run} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
    </div>
  );
}

/** Quick-create a TKT-numbered ticket (the full create lives in the generic runtime). */
export function CreateTicket() {
  const create = useCreateDocument();
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("medium");

  async function run() {
    const trimmed = title.trim();
    if (!trimmed) return;
    try {
      const res = await create.mutateAsync({ entitySlug: "ticket", data: { title: trimmed, priority } });
      toast.success(res.number ? `Created ${res.number}` : "Ticket created");
      setTitle("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Quick create ticket</h2>
        <p className="text-xs text-muted-foreground">
          Create a TKT-numbered ticket with an SLA attached; richer fields are available in the generic
          record runtime.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex-1 space-y-1">
          <span className="text-xs font-medium">Title</span>
          <Input
            aria-label="Ticket title"
            placeholder="Cannot log in to portal"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <div className="w-40 space-y-1">
          <span className="text-xs font-medium">Priority</span>
          <Select value={priority} onValueChange={setPriority}>
            <SelectTrigger aria-label="Ticket priority">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={run} disabled={!title.trim() || create.isPending}>
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
        <h2 className="text-sm font-medium">Ticket lifecycle</h2>
        <p className="text-xs text-muted-foreground">
          Advance a ticket (or ITSM change) by its record id. (Deep per-record action buttons inside the
          generic record runtime are out of scope, so the id is entered here as a raw UUID.)
        </p>
      </div>
      <AssignTicketAction />
      <AutoAssignTicketAction />
      <SetStatusAction />
      <SubmitCsatAction />
      <IdAction label="Escalate a ticket" placeholder="Ticket record id" actionLabel="Escalate" useAction={useEscalateTicket} successText="Ticket escalated" />
      <IdAction label="Resolve a ticket" placeholder="Ticket record id" actionLabel="Resolve" useAction={useResolveTicket} successText="Ticket resolved" />
      <IdAction label="Close a ticket" placeholder="Ticket record id" actionLabel="Close" useAction={useCloseTicket} successText="Ticket closed" />
      <IdAction label="Approve a change" placeholder="Change record id" actionLabel="Approve" useAction={useApproveChange} successText="Change approved" />
    </div>
  );
}

/** Assign a ticket to an agent and/or team. */
export function AssignTicketAction() {
  const assign = useAssignTicket();
  const [id, setId] = useState("");
  const [agent, setAgent] = useState("");
  const [team, setTeam] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await assign.mutateAsync({
        recordId,
        agent: agent.trim() || undefined,
        team: team.trim() || undefined,
      });
      toast.success("Ticket assigned");
      setId("");
      setAgent("");
      setTeam("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Assign failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Assign a ticket</span>
        <Input aria-label="Assign a ticket" placeholder="Ticket record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <label className="w-40 space-y-1">
        <span className="text-xs font-medium">Agent id</span>
        <Input aria-label="Agent id" placeholder="agent (raw UUID)" value={agent} onChange={(e) => setAgent(e.target.value)} />
      </label>
      <label className="w-40 space-y-1">
        <span className="text-xs font-medium">Team id</span>
        <Input aria-label="Team id" placeholder="team (raw UUID)" value={team} onChange={(e) => setTeam(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || assign.isPending}>
        {assign.isPending ? "Working…" : "Assign"}
      </Button>
    </div>
  );
}

/** Auto-assign a ticket via a chosen strategy. */
export function AutoAssignTicketAction() {
  const auto = useAutoAssignTicket();
  const [id, setId] = useState("");
  const [method, setMethod] = useState<AutoAssignMethod>("round_robin");
  const [team, setTeam] = useState("");
  const [skill, setSkill] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await auto.mutateAsync({
        recordId,
        method,
        team: team.trim() || undefined,
        skill: skill.trim() || undefined,
      });
      toast.success("Ticket auto-assigned");
      setId("");
      setTeam("");
      setSkill("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Auto-assign failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Auto-assign a ticket</span>
        <Input aria-label="Auto-assign a ticket" placeholder="Ticket record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="w-44 space-y-1">
        <span className="text-xs font-medium">Method</span>
        <Select value={method} onValueChange={(v) => setMethod(v as AutoAssignMethod)}>
          <SelectTrigger aria-label="Auto-assign method">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="round_robin">Round robin</SelectItem>
            <SelectItem value="load_based">Load based</SelectItem>
            <SelectItem value="skill_based">Skill based</SelectItem>
            <SelectItem value="team_based">Team based</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <label className="w-36 space-y-1">
        <span className="text-xs font-medium">Team</span>
        <Input aria-label="Auto-assign team id" placeholder="optional" value={team} onChange={(e) => setTeam(e.target.value)} />
      </label>
      <label className="w-36 space-y-1">
        <span className="text-xs font-medium">Skill</span>
        <Input aria-label="Auto-assign skill" placeholder="optional" value={skill} onChange={(e) => setSkill(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || auto.isPending}>
        {auto.isPending ? "Working…" : "Auto-assign"}
      </Button>
    </div>
  );
}

/** Change a ticket's status. */
export function SetStatusAction() {
  const setStatus = useSetTicketStatus();
  const [id, setId] = useState("");
  const [status, setStatusValue] = useState<string>("in_progress");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await setStatus.mutateAsync({ recordId, status });
      toast.success("Ticket status updated");
      setId("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Status change failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Set ticket status</span>
        <Input aria-label="Set ticket status" placeholder="Ticket record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="w-44 space-y-1">
        <span className="text-xs font-medium">Status</span>
        <Select value={status} onValueChange={setStatusValue}>
          <SelectTrigger aria-label="Ticket status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TICKET_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s.replace(/_/g, " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button onClick={run} disabled={!id.trim() || setStatus.isPending}>
        {setStatus.isPending ? "Working…" : "Set status"}
      </Button>
    </div>
  );
}

/** Submit a CSAT response for a ticket. */
export function SubmitCsatAction() {
  const csat = useSubmitCsat();
  const [id, setId] = useState("");
  const [rating, setRating] = useState("5");
  const [comments, setComments] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    const ratingNum = Number(rating);
    if (!Number.isFinite(ratingNum)) {
      toast.error("Enter a numeric rating");
      return;
    }
    try {
      await csat.mutateAsync({ recordId, rating: ratingNum, comments: comments.trim() || undefined });
      toast.success("CSAT submitted");
      setId("");
      setComments("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "CSAT failed");
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">Submit CSAT</span>
        <Input aria-label="Submit CSAT" placeholder="Ticket record id" value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="w-32 space-y-1">
        <span className="text-xs font-medium">Rating</span>
        <Select value={rating} onValueChange={setRating}>
          <SelectTrigger aria-label="CSAT rating">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[1, 2, 3, 4, 5].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <label className="w-48 space-y-1">
        <span className="text-xs font-medium">Comments</span>
        <Input aria-label="CSAT comments" placeholder="optional" value={comments} onChange={(e) => setComments(e.target.value)} />
      </label>
      <Button onClick={run} disabled={!id.trim() || csat.isPending}>
        {csat.isPending ? "Working…" : "Submit"}
      </Button>
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

export { HELPDESK_SLUG, MODULES, ENGINE_LINKS };
