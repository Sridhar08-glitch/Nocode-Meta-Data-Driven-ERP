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
const assign = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const ret = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const transfer = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const inspect = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const retire = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeWO = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/assets/hooks", () => ({
  useEnsureSetup: () => setup,
  useAssignAsset: () => assign,
  useReturnAsset: () => ret,
  useTransferAsset: () => transfer,
  useInspectAsset: () => inspect,
  useRetireAsset: () => retire,
  useCompleteWorkOrder: () => completeWO,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { AssetsOverview } from "./assets-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "assets", solution_name: "Assets",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 13, forms: 4, views: 6, workflows: 3, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("AssetsOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<AssetsOverview />);
    expect(screen.getByText("Asset Management isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Assign an asset")).not.toBeInTheDocument();
  });
});

describe("AssetsOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each module's entities to its generic record screen", () => {
    render(<AssetsOverview />);
    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("href", "/e/asset");
    expect(screen.getByRole("link", { name: "Categories" })).toHaveAttribute("href", "/e/asset_category");
    expect(screen.getByRole("link", { name: "Assignments" })).toHaveAttribute("href", "/e/asset_assignment");
    expect(screen.getByRole("link", { name: "Work orders" })).toHaveAttribute("href", "/e/maintenance_work_order");
    expect(screen.getByRole("link", { name: "Warranties" })).toHaveAttribute("href", "/e/warranty");
  });

  it("exposes the native engine pages + dashboards/reports (no orphaned area)", () => {
    render(<AssetsOverview />);
    expect(screen.getByRole("link", { name: /Depreciation/ })).toHaveAttribute("href", "/assets/depreciation");
    expect(screen.getByRole("link", { name: /Disposals/ })).toHaveAttribute("href", "/assets/disposals");
    expect(screen.getByRole("link", { name: "Dashboards" })).toHaveAttribute("href", "/dashboards");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports");
  });

  it("assigns an asset by record id + employee id", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Assign an asset"), { target: { value: "a-9" } });
    fireEvent.change(screen.getByLabelText("Assign an asset employee"), { target: { value: "emp-1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Assign" })[0]);
    await waitFor(() =>
      expect(assign.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "a-9", data: { employee: "emp-1" } })),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("returns an asset by record id", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Return an asset"), { target: { value: "a-3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Return" })[0]);
    await waitFor(() => expect(ret.mutateAsync).toHaveBeenCalledWith(arg("a-3")));
  });

  it("transfers an asset with type + from/to", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Transfer an asset"), { target: { value: "a-1" } });
    fireEvent.change(screen.getByLabelText("Transfer from"), { target: { value: "loc-A" } });
    fireEvent.change(screen.getByLabelText("Transfer to"), { target: { value: "loc-B" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Transfer" })[0]);
    await waitFor(() =>
      expect(transfer.mutateAsync).toHaveBeenCalledWith(
        arg({ recordId: "a-1", data: { transfer_type: "location", from_ref: "loc-A", to_ref: "loc-B" } }),
      ),
    );
  });

  it("records an inspection result", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Inspect an asset"), { target: { value: "a-5" } });
    fireEvent.change(screen.getByLabelText("Inspection notes"), { target: { value: "ok" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Inspect" })[0]);
    await waitFor(() =>
      expect(inspect.mutateAsync).toHaveBeenCalledWith(arg({ recordId: "a-5", data: { result: "passed", notes: "ok" } })),
    );
  });

  it("retires an asset by record id + reason", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Retire an asset"), { target: { value: "a-7" } });
    fireEvent.change(screen.getByLabelText("Retire reason"), { target: { value: "End of life" } });
    fireEvent.change(screen.getByLabelText("Residual value"), { target: { value: "100" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Retire" })[0]);
    await waitFor(() =>
      expect(retire.mutateAsync).toHaveBeenCalledWith(
        arg({ recordId: "a-7", data: { reason: "End of life", residual_value: "100" } }),
      ),
    );
  });

  it("completes a work order by record id", async () => {
    render(<AssetsOverview />);
    fireEvent.change(screen.getByLabelText("Complete a work order"), { target: { value: "wo-2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Complete" })[0]);
    await waitFor(() => expect(completeWO.mutateAsync).toHaveBeenCalledWith(arg("wo-2")));
  });

  it("runs setup as an admin", async () => {
    render(<AssetsOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<AssetsOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Assign an asset")).toBeInTheDocument();
  });
});
