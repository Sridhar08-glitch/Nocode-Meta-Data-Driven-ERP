import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Bom } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const bomsQ = { isLoading: false, isError: false, data: [] as Bom[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approve = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useBoms: () => bomsQ,
  useCreateBom: () => create,
  useApproveBom: () => approve,
  useCanManageManufacturing: () => canManage,
}));

import { BomsPanel } from "./boms-panel";

const bom = (over: Partial<Bom> = {}): Bom => ({
  id: "b1", number: "BOM-0001", product_item_id: "prod-1", quantity: "1",
  revision: "A", status: "draft", ...over,
});

beforeEach(() => {
  bomsQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("BomsPanel", () => {
  it("lists BOMs with status", () => {
    bomsQ.data = [bom({ status: "active" })];
    render(<BomsPanel />);
    expect(screen.getByText("BOM-0001")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("creates a BOM with components", async () => {
    render(<BomsPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New BOM" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Product item id"), { target: { value: "prod-9" } });
    fireEvent.change(within(dialog).getByLabelText("Component item id"), { target: { value: "comp-1" } });
    fireEvent.change(within(dialog).getByLabelText("Qty"), { target: { value: "3" } });
    fireEvent.change(within(dialog).getByLabelText("Scrap %"), { target: { value: "5" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          product_item_id: "prod-9",
          quantity: "1",
          revision: "A",
          components: [{ component_item_id: "comp-1", quantity: "3", scrap_percent: "5" }],
        }),
      ),
    );
  });

  it("adds a second component row before saving", async () => {
    render(<BomsPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New BOM" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Product item id"), { target: { value: "prod-9" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add component" }));
    const items = within(dialog).getAllByLabelText("Component item id");
    expect(items).toHaveLength(2);
    fireEvent.change(items[0], { target: { value: "comp-1" } });
    fireEvent.change(items[1], { target: { value: "comp-2" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          components: [
            { component_item_id: "comp-1", quantity: "1", scrap_percent: "0" },
            { component_item_id: "comp-2", quantity: "1", scrap_percent: "0" },
          ],
        }),
      ),
    );
  });

  it("approves a draft BOM", async () => {
    bomsQ.data = [bom({ status: "draft" })];
    render(<BomsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(approve.mutateAsync).toHaveBeenCalledWith("b1"));
  });

  it("does not show Approve for an active BOM", () => {
    bomsQ.data = [bom({ status: "active" })];
    render(<BomsPanel />);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("hides create and approve for non-admins", () => {
    canManage = false;
    bomsQ.data = [bom({ status: "draft" })];
    render(<BomsPanel />);
    expect(screen.queryByRole("button", { name: "New BOM" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });
});
