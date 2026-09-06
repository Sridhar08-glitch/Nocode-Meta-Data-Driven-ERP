import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BomExplosion } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const setup = { mutateAsync: vi.fn(() => Promise.resolve({ detail: "ok" })), isPending: false };
const explodeQ = { isLoading: false, isError: false, data: undefined as BomExplosion | undefined };
const explodeSpy = vi.fn();
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useRunSetup: () => setup,
  useExplodeBom: (productId: string | undefined, qty: string) => {
    explodeSpy(productId, qty);
    return explodeQ;
  },
  useCanManageManufacturing: () => canManage,
}));

import { BomExplodePreview, ManufacturingOverview } from "./manufacturing-overview";

beforeEach(() => {
  explodeQ.data = undefined;
  canManage = true;
  vi.clearAllMocks();
});

describe("ManufacturingOverview", () => {
  it("runs setup", async () => {
    render(<ManufacturingOverview />);
    fireEvent.click(screen.getByRole("button", { name: "Run setup" }));
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalled());
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("ok"));
  });

  it("hides Run setup for non-admins", () => {
    canManage = false;
    render(<ManufacturingOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
  });
});

describe("BomExplodePreview", () => {
  it("explodes a BOM and renders the requirements", async () => {
    explodeQ.data = { requirements: { "comp-a": "6", "comp-b": "12" } };
    render(<BomExplodePreview />);
    fireEvent.change(screen.getByLabelText("Product item id"), { target: { value: "prod-1" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Explode" }));
    // The active product/qty are passed to the explode hook.
    await waitFor(() => expect(explodeSpy).toHaveBeenCalledWith("prod-1", "3"));
    expect(screen.getByText("comp-a")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });

  it("shows an empty message when there are no requirements", async () => {
    explodeQ.data = { requirements: {} };
    render(<BomExplodePreview />);
    fireEvent.change(screen.getByLabelText("Product item id"), { target: { value: "prod-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Explode" }));
    await waitFor(() => expect(screen.getByText(/no active BOM/i)).toBeInTheDocument());
  });
});
