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
const hire = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeInterview = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const acceptOffer = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveLeave = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const rejectLeave = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completePerf = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const promote = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const transfer = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const offboard = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/hr/hooks", () => ({
  useEnsureSetup: () => setup,
  useHireCandidate: () => hire,
  useCompleteInterview: () => completeInterview,
  useAcceptOffer: () => acceptOffer,
  useApproveLeave: () => approveLeave,
  useRejectLeave: () => rejectLeave,
  useCompletePerformance: () => completePerf,
  usePromoteEmployee: () => promote,
  useTransferEmployee: () => transfer,
  useOffboardEmployee: () => offboard,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { HrOverview } from "./hr-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "hr", solution_name: "HR",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 28, forms: 6, views: 8, workflows: 4, rules: 2, reports: 3, roles: 3, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("HrOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<HrOverview />);
    expect(screen.getByText("HR isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Hire a candidate")).not.toBeInTheDocument();
  });
});

describe("HrOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each module's entities to its generic record screen", () => {
    render(<HrOverview />);
    expect(screen.getByRole("link", { name: "Candidates" })).toHaveAttribute("href", "/e/candidate");
    expect(screen.getByRole("link", { name: "Employees" })).toHaveAttribute("href", "/e/employee");
    expect(screen.getByRole("link", { name: "Leave requests" })).toHaveAttribute("href", "/e/leave_request");
    expect(screen.getByRole("link", { name: "Promotions" })).toHaveAttribute("href", "/e/promotion");
  });

  it("reaches every HR entity + dashboards/reports (no orphaned area)", () => {
    render(<HrOverview />);
    // Previously-orphaned entities are now linked.
    expect(screen.getByRole("link", { name: "Job grades" })).toHaveAttribute("href", "/e/job_grade");
    expect(screen.getByRole("link", { name: "Leave balances" })).toHaveAttribute("href", "/e/leave_balance");
    expect(screen.getByRole("link", { name: "Clearances" })).toHaveAttribute("href", "/e/clearance");
    // Dashboards + reports are reachable from the HR area.
    expect(screen.getByRole("link", { name: "Dashboards" })).toHaveAttribute("href", "/dashboards");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports");
  });

  it("hires a candidate by record id", async () => {
    render(<HrOverview />);
    fireEvent.change(screen.getByLabelText("Hire a candidate"), { target: { value: "c-9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Hire" })[0]);
    await waitFor(() => expect(hire.mutateAsync).toHaveBeenCalledWith(arg("c-9")));
    expect(toast.success).toHaveBeenCalled();
  });

  it("approves a leave request by record id", async () => {
    render(<HrOverview />);
    fireEvent.change(screen.getByLabelText("Approve a leave request"), { target: { value: "lr-1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(approveLeave.mutateAsync).toHaveBeenCalledWith(arg("lr-1")));
  });

  it("promotes an employee with id + new position", async () => {
    render(<HrOverview />);
    fireEvent.change(screen.getByLabelText("Promote an employee"), { target: { value: "e-1" } });
    fireEvent.change(screen.getByLabelText("Promote an employee new position"), { target: { value: "pos-9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Promote" })[0]);
    await waitFor(() =>
      expect(promote.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "e-1", newPosition: "pos-9" })),
    );
  });

  it("transfers an employee with id + new department", async () => {
    render(<HrOverview />);
    fireEvent.change(screen.getByLabelText("Transfer an employee"), { target: { value: "e-2" } });
    fireEvent.change(screen.getByLabelText("Transfer an employee new department"), { target: { value: "dep-4" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Transfer" })[0]);
    await waitFor(() =>
      expect(transfer.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "e-2", newDepartment: "dep-4" })),
    );
  });

  it("runs setup as an admin", async () => {
    render(<HrOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<HrOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Hire a candidate")).toBeInTheDocument();
  });
});
