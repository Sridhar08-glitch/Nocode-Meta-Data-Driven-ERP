import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WebhookSubscription } from "@/lib/integrations/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const subsQ = { isLoading: false, isError: false, data: { results: [] as WebhookSubscription[], count: 0 } };
const deliveriesQ = { isLoading: false, data: { results: [], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const test = { mutateAsync: vi.fn(() => Promise.resolve({ delivered: true, delivery: { response_status: 200 } })), isPending: false };
const toggle = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/integrations/hooks", () => ({
  useSubscriptions: () => subsQ,
  useCreateSub: () => create,
  useDeleteSub: () => del,
  useTestSub: () => test,
  useToggleSub: () => toggle,
  useDeliveries: () => deliveriesQ,
}));

import { WebhookBuilder } from "./webhook-builder";

const sub = (over: Partial<WebhookSubscription> = {}): WebhookSubscription => ({
  id: "s1", name: "Slack", target_url: "https://hooks.slack.com/x", signing_secret_ref: "", event_types: ["record.created"],
  entity_id: null, status: "active", http_method: "POST", headers: {}, timeout_seconds: 10, max_retries: 5,
  success_count: 3, failure_count: 0, consecutive_failures: 0, last_fired_at: null, ...over,
});

beforeEach(() => {
  subsQ.data = { results: [], count: 0 };
  for (const m of [create, del, test, toggle]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("WebhookBuilder", () => {
  it("creates a webhook with parsed event types", async () => {
    render(<WebhookBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New webhook" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Slack" } });
    fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://hooks.slack.com/x" } });
    fireEvent.change(screen.getByLabelText("Event types (comma-separated)"), { target: { value: "record.created, record.updated" } });
    fireEvent.click(screen.getByRole("button", { name: "Create webhook" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ target_url: "https://hooks.slack.com/x", event_types: ["record.created", "record.updated"] }));
  });

  it("requires a valid https URL before enabling save", () => {
    render(<WebhookBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New webhook" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Bad" } });
    fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "ftp://nope" } });
    fireEvent.change(screen.getByLabelText("Event types (comma-separated)"), { target: { value: "x" } });
    expect(screen.getByRole("button", { name: "Create webhook" })).toBeDisabled();
  });

  it("tests and disables a webhook", async () => {
    subsQ.data = { results: [sub()], count: 1 };
    render(<WebhookBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Test Slack" }));
    await waitFor(() => expect(test.mutateAsync).toHaveBeenCalledWith("s1"));
    fireEvent.click(screen.getByRole("button", { name: "Disable Slack" }));
    await waitFor(() => expect(toggle.mutateAsync).toHaveBeenCalledWith({ id: "s1", enable: false }));
  });
});
