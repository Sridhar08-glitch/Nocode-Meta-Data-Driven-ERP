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
const postGr = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const postVb = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/procurement/hooks", () => ({
  useEnsureSetup: () => setup,
  usePostGoodsReceipt: () => postGr,
  usePostVendorBill: () => postVb,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { ProcurementOverview } from "./procurement-overview";

const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "procurement", solution_name: "Procurement",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 6, forms: 3, views: 5, workflows: 2, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1"], created_application_ids: ["a1"], created_at: "", ...over,
});

// mock mutateAsync args are `never`-typed in this harness → cast through unknown.
const arg = (v: unknown) => v as never;

beforeEach(() => {
  installedQ.data = { results: [], count: 0 };
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("ProcurementOverview — not installed", () => {
  it("shows the install empty-state with links to the solution catalog/wizard", () => {
    render(<ProcurementOverview />);
    expect(screen.getByText("Procurement isn't installed yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse solutions" })).toHaveAttribute("href", "/solutions");
    expect(screen.getByRole("link", { name: "Create solution" })).toHaveAttribute("href", "/solutions/new");
    // lifecycle actions absent until installed
    expect(screen.queryByLabelText("Post goods receipt")).not.toBeInTheDocument();
  });
});

describe("ProcurementOverview — installed", () => {
  beforeEach(() => {
    installedQ.data = { results: [installed()], count: 1 };
  });

  it("links each lifecycle stage to its generic record screen", () => {
    render(<ProcurementOverview />);
    expect(screen.getByRole("link", { name: /Vendors/ })).toHaveAttribute("href", "/e/vendor");
    expect(screen.getByRole("link", { name: /Purchase orders/ })).toHaveAttribute("href", "/e/purchase_order");
    expect(screen.getByRole("link", { name: /Goods receipts/ })).toHaveAttribute("href", "/e/goods_receipt");
    expect(screen.getByRole("link", { name: /Vendor bills/ })).toHaveAttribute("href", "/e/vendor_bill");
  });

  it("posts a goods receipt by record id", async () => {
    render(<ProcurementOverview />);
    fireEvent.change(screen.getByLabelText("Post goods receipt"), { target: { value: "gr-9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Post" })[0]);
    await waitFor(() => expect(postGr.mutateAsync).toHaveBeenCalledWith(arg("gr-9")));
    expect(toast.success).toHaveBeenCalled();
  });

  it("posts a vendor bill by record id", async () => {
    render(<ProcurementOverview />);
    fireEvent.change(screen.getByLabelText("Post vendor bill"), { target: { value: "vb-3" } });
    // second "Post" button is the vendor-bill action
    fireEvent.click(screen.getAllByRole("button", { name: "Post" })[1]);
    await waitFor(() => expect(postVb.mutateAsync).toHaveBeenCalledWith(arg("vb-3")));
  });

  it("runs setup as an admin", async () => {
    render(<ProcurementOverview />);
    fireEvent.click(screen.getAllByRole("button", { name: "Run setup" })[0]);
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith("ready");
  });

  it("hides Run setup for non-admins", () => {
    tenant.workspace = { role: "member" };
    render(<ProcurementOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    // lifecycle post actions remain available to members (the API gates them)
    expect(screen.getByLabelText("Post goods receipt")).toBeInTheDocument();
  });
});
