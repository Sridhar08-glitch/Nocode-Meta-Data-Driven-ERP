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
const createDoc = { mutateAsync: vi.fn(() => Promise.resolve({ id: "p1", number: "PRJ-1" })), isPending: false };
const startProject = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeProject = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const baseline = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveBudget = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeTask = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeMilestone = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveTimesheet = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveExpense = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveCR = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveDeliverable = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/projects/hooks", () => ({
  useEnsureSetup: () => setup,
  useCreateDocument: () => createDoc,
  useStartProject: () => startProject,
  useCompleteProject: () => completeProject,
  useBaselineProject: () => baseline,
  useApproveBudget: () => approveBudget,
  useCompleteTask: () => completeTask,
  useCompleteMilestone: () => completeMilestone,
  useApproveTimesheet: () => approveTimesheet,
  useApproveExpense: () => approveExpense,
  useApproveChangeRequest: () => approveCR,
  useApproveDeliverable: () => approveDeliverable,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { ProjectsOverview } from "./projects-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "projects", solution_name: "Projects",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 16, forms: 4, views: 6, workflows: 3, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("ProjectsOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<ProjectsOverview />);
    expect(screen.getByText("Project Management isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Start a project")).not.toBeInTheDocument();
  });
});

describe("ProjectsOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each module's entities to its generic record screen", () => {
    render(<ProjectsOverview />);
    expect(screen.getByRole("link", { name: "Portfolios" })).toHaveAttribute("href", "/e/portfolio");
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/e/project");
    expect(screen.getByRole("link", { name: "Tasks" })).toHaveAttribute("href", "/e/task");
    expect(screen.getByRole("link", { name: "Timesheets" })).toHaveAttribute("href", "/e/timesheet");
    expect(screen.getByRole("link", { name: "Change requests" })).toHaveAttribute("href", "/e/change_request");
  });

  it("exposes the native engine pages + dashboards/reports (no orphaned area)", () => {
    render(<ProjectsOverview />);
    expect(screen.getByRole("link", { name: /Financials/ })).toHaveAttribute("href", "/projects/financials");
    expect(screen.getByRole("link", { name: /Schedule/ })).toHaveAttribute("href", "/projects/schedule");
    expect(screen.getByRole("link", { name: /Resources/ })).toHaveAttribute("href", "/projects/resources");
    expect(screen.getByRole("link", { name: "Dashboards" })).toHaveAttribute("href", "/dashboards");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports");
  });

  it("quick-creates a project document", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Document name"), { target: { value: "Website rebuild" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Create" })[0]);
    await waitFor(() =>
      expect(createDoc.mutateAsync).toHaveBeenCalledWith(
        arg({ entitySlug: "project", data: { name: "Website rebuild" } }),
      ),
    );
    expect(toast.success).toHaveBeenCalledWith("Created PRJ-1");
  });

  it("starts a project by record id", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Start a project"), { target: { value: "pr-9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Start" })[0]);
    await waitFor(() => expect(startProject.mutateAsync).toHaveBeenCalledWith(arg("pr-9")));
    expect(toast.success).toHaveBeenCalled();
  });

  it("baselines a project by record id", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Baseline a project"), { target: { value: "pr-2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Baseline" })[0]);
    await waitFor(() => expect(baseline.mutateAsync).toHaveBeenCalledWith(arg("pr-2")));
  });

  it("approves a budget by project record id", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Approve a budget"), { target: { value: "pr-3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(approveBudget.mutateAsync).toHaveBeenCalledWith(arg("pr-3")));
  });

  it("completes a task by record id", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Complete a task"), { target: { value: "tk-1" } });
    // two "Complete" buttons (project + task + milestone) — task is the 2nd Complete button
    const completeButtons = screen.getAllByRole("button", { name: "Complete" });
    fireEvent.click(completeButtons[1]);
    await waitFor(() => expect(completeTask.mutateAsync).toHaveBeenCalledWith(arg("tk-1")));
  });

  it("approves a deliverable by record id", async () => {
    render(<ProjectsOverview />);
    fireEvent.change(screen.getByLabelText("Approve a deliverable"), { target: { value: "dl-1" } });
    // last Approve button is the deliverable
    const approveButtons = screen.getAllByRole("button", { name: "Approve" });
    fireEvent.click(approveButtons[approveButtons.length - 1]);
    await waitFor(() => expect(approveDeliverable.mutateAsync).toHaveBeenCalledWith(arg("dl-1")));
  });

  it("runs setup as an admin", async () => {
    render(<ProjectsOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<ProjectsOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Start a project")).toBeInTheDocument();
  });
});
