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
const qualify = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const win = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const lose = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const complete = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/crm/hooks", () => ({
  useEnsureSetup: () => setup,
  useQualifyLead: () => qualify,
  useWinOpportunity: () => win,
  useLoseOpportunity: () => lose,
  useCompleteActivity: () => complete,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { CrmOverview } from "./crm-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "crm", solution_name: "CRM",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 5, forms: 3, views: 5, workflows: 2, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("CrmOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<CrmOverview />);
    expect(screen.getByText("CRM isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Qualify a lead")).not.toBeInTheDocument();
  });
});

describe("CrmOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each pipeline stage to its generic record screen", () => {
    render(<CrmOverview />);
    expect(screen.getByRole("link", { name: /Leads/ })).toHaveAttribute("href", "/e/lead");
    expect(screen.getByRole("link", { name: /Accounts/ })).toHaveAttribute("href", "/e/account");
    expect(screen.getByRole("link", { name: /Contacts/ })).toHaveAttribute("href", "/e/contact");
    expect(screen.getByRole("link", { name: /Opportunities/ })).toHaveAttribute("href", "/e/opportunity");
    expect(screen.getByRole("link", { name: /Activities/ })).toHaveAttribute("href", "/e/activity");
  });

  it("qualifies a lead by record id", async () => {
    render(<CrmOverview />);
    fireEvent.change(screen.getByLabelText("Qualify a lead"), { target: { value: "lead-9" } });
    fireEvent.click(screen.getByRole("button", { name: "Qualify" }));
    await waitFor(() => expect(qualify.mutateAsync).toHaveBeenCalledWith(arg("lead-9")));
    expect(toast.success).toHaveBeenCalled();
  });

  it("wins an opportunity with id + reason", async () => {
    render(<CrmOverview />);
    fireEvent.change(screen.getByLabelText("Win an opportunity"), { target: { value: "opp-1" } });
    fireEvent.change(screen.getByLabelText("Win an opportunity reason"), { target: { value: "list price" } });
    fireEvent.click(screen.getByRole("button", { name: "Win" }));
    await waitFor(() =>
      expect(win.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "opp-1", reason: "list price" })),
    );
  });

  it("loses an opportunity with id + reason", async () => {
    render(<CrmOverview />);
    fireEvent.change(screen.getByLabelText("Lose an opportunity"), { target: { value: "opp-2" } });
    fireEvent.change(screen.getByLabelText("Lose an opportunity reason"), { target: { value: "lost to comp" } });
    fireEvent.click(screen.getByRole("button", { name: "Lose" }));
    await waitFor(() =>
      expect(lose.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "opp-2", reason: "lost to comp" })),
    );
  });

  it("completes an activity by record id", async () => {
    render(<CrmOverview />);
    fireEvent.change(screen.getByLabelText("Complete an activity"), { target: { value: "act-3" } });
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));
    await waitFor(() => expect(complete.mutateAsync).toHaveBeenCalledWith(arg("act-3")));
  });

  it("runs setup as an admin", async () => {
    render(<CrmOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<CrmOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Qualify a lead")).toBeInTheDocument();
  });
});
