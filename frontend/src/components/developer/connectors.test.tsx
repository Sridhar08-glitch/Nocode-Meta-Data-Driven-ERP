import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HTTPConnector } from "@/lib/integrations/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const connQ = { isLoading: false, isError: false, data: { results: [] as HTTPConnector[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const test = { mutateAsync: vi.fn(() => Promise.resolve({ status: 200 })), isPending: false };
vi.mock("@/lib/integrations/hooks", () => ({
  useConnectors: () => connQ,
  useCreateConnector: () => create,
  useDeleteConnector: () => del,
  useTestConnector: () => test,
}));

import { Connectors } from "./connectors";

const conn = (over: Partial<HTTPConnector> = {}): HTTPConnector => ({
  id: "c1", name: "Stripe API", slug: "stripe_api", base_url: "https://api.stripe.com", auth_type: "bearer",
  auth_config: {}, timeout_seconds: 10, is_active: true, ...over,
});

beforeEach(() => {
  connQ.data = { results: [], count: 0 };
  for (const m of [create, del, test]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("Connectors", () => {
  it("creates a connector with an auto-slug", async () => {
    render(<Connectors />);
    fireEvent.click(screen.getAllByRole("button", { name: "New connector" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Stripe API" } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://api.stripe.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Create connector" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ slug: "stripe_api", base_url: "https://api.stripe.com" }));
  });

  it("tests a connector", async () => {
    connQ.data = { results: [conn()], count: 1 };
    render(<Connectors />);
    fireEvent.click(screen.getByRole("button", { name: "Test Stripe API" }));
    await waitFor(() => expect(test.mutateAsync).toHaveBeenCalledWith("c1"));
  });
});
