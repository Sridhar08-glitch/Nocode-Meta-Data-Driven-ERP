import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InstalledSolution } from "@/lib/solution-templates/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const installedQ = { isLoading: false, isError: false, data: { results: [] as InstalledSolution[], count: 0 } };
vi.mock("@/lib/solution-templates/hooks", () => ({
  useInstalledSolutions: () => installedQ,
}));

const setup = { mutateAsync: vi.fn(() => Promise.resolve({ detail: "ready" })), isPending: false };
const createDoc = { mutateAsync: vi.fn(() => Promise.resolve({ id: "t1", number: "TKT-1" })), isPending: false };
const assign = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const autoAssign = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const escalate = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const setStatus = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const resolve = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const close = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const csat = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveChange = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/helpdesk/hooks", () => ({
  useEnsureSetup: () => setup,
  useCreateDocument: () => createDoc,
  useAssignTicket: () => assign,
  useAutoAssignTicket: () => autoAssign,
  useEscalateTicket: () => escalate,
  useSetTicketStatus: () => setStatus,
  useResolveTicket: () => resolve,
  useCloseTicket: () => close,
  useSubmitCsat: () => csat,
  useApproveChange: () => approveChange,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { HelpdeskOverview } from "./helpdesk-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "helpdesk", solution_name: "Helpdesk",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 12, forms: 4, views: 6, workflows: 3, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("HelpdeskOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<HelpdeskOverview />);
    expect(screen.getByText("Helpdesk isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Assign a ticket")).not.toBeInTheDocument();
  });
});

describe("HelpdeskOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each module's entities to its generic record screen", () => {
    render(<HelpdeskOverview />);
    expect(screen.getByRole("link", { name: "Tickets" })).toHaveAttribute("href", "/e/ticket");
    expect(screen.getByRole("link", { name: "Categories" })).toHaveAttribute("href", "/e/ticket_category");
    expect(screen.getByRole("link", { name: "Problems" })).toHaveAttribute("href", "/e/problem");
    expect(screen.getByRole("link", { name: "Changes" })).toHaveAttribute("href", "/e/itsm_change");
    expect(screen.getByRole("link", { name: "Knowledge base" })).toHaveAttribute("href", "/e/kb_article");
    expect(screen.getByRole("link", { name: "Agent profiles" })).toHaveAttribute("href", "/e/agent_profile");
  });

  it("exposes the native engine pages + dashboards/reports (no orphaned area)", () => {
    render(<HelpdeskOverview />);
    expect(screen.getByRole("link", { name: /Knowledge recommendation/ })).toHaveAttribute(
      "href",
      "/helpdesk/knowledge",
    );
    expect(screen.getByRole("link", { name: /SLA dashboard/ })).toHaveAttribute("href", "/helpdesk/sla");
    expect(screen.getByRole("link", { name: "Dashboards" })).toHaveAttribute("href", "/dashboards");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports");
  });

  it("quick-creates a ticket with a title + priority", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Ticket title"), { target: { value: "Cannot log in" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Create" })[0]);
    await waitFor(() =>
      expect(createDoc.mutateAsync).toHaveBeenCalledWith(
        arg({ entitySlug: "ticket", data: { title: "Cannot log in", priority: "medium" } }),
      ),
    );
    expect(toast.success).toHaveBeenCalledWith("Created TKT-1");
  });

  it("assigns a ticket to an agent + team by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Assign a ticket"), { target: { value: "tk-1" } });
    fireEvent.change(screen.getByLabelText("Agent id"), { target: { value: "ag-9" } });
    fireEvent.change(screen.getByLabelText("Team id"), { target: { value: "tm-2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Assign" })[0]);
    await waitFor(() =>
      expect(assign.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "tk-1", agent: "ag-9", team: "tm-2" })),
    );
  });

  it("auto-assigns a ticket with the chosen method", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Auto-assign a ticket"), { target: { value: "tk-7" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Auto-assign" })[0]);
    await waitFor(() =>
      expect(autoAssign.mutateAsync).toHaveBeenCalledWith(
        arg({ recordId: "tk-7", method: "round_robin", team: undefined, skill: undefined }),
      ),
    );
  });

  it("sets a ticket status by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Set ticket status"), { target: { value: "tk-3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Set status" })[0]);
    await waitFor(() =>
      expect(setStatus.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "tk-3", status: "in_progress" })),
    );
  });

  it("submits CSAT for a ticket", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Submit CSAT"), { target: { value: "tk-5" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Submit" })[0]);
    await waitFor(() =>
      expect(csat.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "tk-5", rating: 5, comments: undefined })),
    );
  });

  it("escalates a ticket by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Escalate a ticket"), { target: { value: "tk-2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Escalate" })[0]);
    await waitFor(() => expect(escalate.mutateAsync).toHaveBeenCalledWith(arg("tk-2")));
  });

  it("resolves a ticket by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Resolve a ticket"), { target: { value: "tk-8" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Resolve" })[0]);
    await waitFor(() => expect(resolve.mutateAsync).toHaveBeenCalledWith(arg("tk-8")));
  });

  it("closes a ticket by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Close a ticket"), { target: { value: "tk-9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Close" })[0]);
    await waitFor(() => expect(close.mutateAsync).toHaveBeenCalledWith(arg("tk-9")));
  });

  it("approves an ITSM change by record id", async () => {
    render(<HelpdeskOverview />);
    fireEvent.change(screen.getByLabelText("Approve a change"), { target: { value: "ch-1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(approveChange.mutateAsync).toHaveBeenCalledWith(arg("ch-1")));
  });

  it("runs setup as an admin", async () => {
    render(<HelpdeskOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<HelpdeskOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Assign a ticket")).toBeInTheDocument();
  });
});
