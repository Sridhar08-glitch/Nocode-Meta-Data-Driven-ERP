import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Disposal } from "@/lib/assets/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const disposalsQ = { isLoading: false, isError: false, data: [] as Disposal[] };
const createDisposal = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/assets/hooks", () => ({
  useDisposals: () => disposalsQ,
  useCreateDisposal: () => createDisposal,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { DisposalPanel } from "./disposal-panel";

const disposal = (over: Partial<Disposal> = {}): Disposal => ({
  id: "d1", asset_record_id: "asset-aaaa-bbbb", method: "sale",
  proceeds: "1500", book_value: "1000", gain_loss: "500", reason: "Sold", ...over,
});

const arg = (v: unknown) => v as never;

beforeEach(() => {
  disposalsQ.data = [];
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("DisposalPanel — admin", () => {
  it("records a disposal with the typed parameters", async () => {
    render(<DisposalPanel />);
    fireEvent.change(screen.getByLabelText("Asset record id"), { target: { value: "asset-9" } });
    fireEvent.change(screen.getByLabelText("Proceeds"), { target: { value: "1500" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Sold to vendor" } });
    fireEvent.click(screen.getByRole("button", { name: "Record disposal" }));
    await waitFor(() =>
      expect(createDisposal.mutateAsync).toHaveBeenCalledWith(
        arg(
          expect.objectContaining({
            asset_record_id: "asset-9",
            method: "sale",
            proceeds: "1500",
            reason: "Sold to vendor",
          }),
        ),
      ),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("requires an asset id and reason", async () => {
    render(<DisposalPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Record disposal" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(createDisposal.mutateAsync).not.toHaveBeenCalled();
  });

  it("renders disposals with the server-computed gain/loss", () => {
    disposalsQ.data = [disposal()];
    render(<DisposalPanel />);
    expect(screen.getByText("500")).toBeInTheDocument();
    expect(screen.getByText("Sold")).toBeInTheDocument();
  });
});

describe("DisposalPanel — non-admin", () => {
  it("hides the create form for non-admins (API also gates it)", () => {
    tenant.workspace = { role: "member" };
    render(<DisposalPanel />);
    expect(screen.queryByRole("button", { name: "Record disposal" })).not.toBeInTheDocument();
    // the disposals list remains visible
    expect(screen.getByLabelText("Filter disposals by asset record id")).toBeInTheDocument();
  });
});
