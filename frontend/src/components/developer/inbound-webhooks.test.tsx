import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InboundWebhook } from "@/lib/integrations/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const inboundQ = { isLoading: false, isError: false, data: { results: [] as InboundWebhook[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({ token: "tok-create", url: "/api/v1/webhooks/inbound/tok-create/" })), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const rotate = { mutateAsync: vi.fn(() => Promise.resolve({ token: "tok-rotated", url: "/api/v1/webhooks/inbound/tok-rotated/" })), isPending: false };
vi.mock("@/lib/integrations/hooks", () => ({
  useInboundWebhooks: () => inboundQ,
  useCreateInbound: () => create,
  useDeleteInbound: () => del,
  useRotateInbound: () => rotate,
}));

import { InboundWebhooks } from "./inbound-webhooks";

const wh = (over: Partial<InboundWebhook> = {}): InboundWebhook => ({
  id: "w1", name: "Stripe", slug: "stripe", workflow_id: null, is_active: true, allowed_ips: [],
  expected_content_type: "", call_count: 0, last_called_at: null, ...over,
});

beforeEach(() => {
  inboundQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear().mockResolvedValue({ token: "tok-create", url: "/api/v1/webhooks/inbound/tok-create/" });
  rotate.mutateAsync.mockClear().mockResolvedValue({ token: "tok-rotated", url: "/api/v1/webhooks/inbound/tok-rotated/" });
  del.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("InboundWebhooks", () => {
  it("creates an inbound webhook and reveals the token once", async () => {
    render(<InboundWebhooks />);
    fireEvent.click(screen.getAllByRole("button", { name: "New inbound" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Stripe Events" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ slug: "stripe_events" })));
    expect(await screen.findByLabelText("Inbound token")).toHaveTextContent("tok-create");
  });

  it("rotates the token and reveals the new one", async () => {
    inboundQ.data = { results: [wh()], count: 1 };
    render(<InboundWebhooks />);
    fireEvent.click(screen.getByRole("button", { name: "Rotate token Stripe" }));
    await waitFor(() => expect(rotate.mutateAsync).toHaveBeenCalledWith("w1"));
    expect(await screen.findByLabelText("Inbound token")).toHaveTextContent("tok-rotated");
  });
});
