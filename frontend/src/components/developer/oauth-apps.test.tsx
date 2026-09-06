import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OAuthApp } from "@/lib/integrations/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const appsQ = { isLoading: false, isError: false, data: { results: [] as OAuthApp[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/integrations/hooks", () => ({
  useOAuthApps: () => appsQ,
  useCreateOAuth: () => create,
  useDeleteOAuth: () => del,
}));

import { OAuthApps } from "./oauth-apps";

beforeEach(() => {
  appsQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear();
  del.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("OAuthApps", () => {
  it("creates an OAuth app with parsed scopes", async () => {
    render(<OAuthApps />);
    fireEvent.click(screen.getAllByRole("button", { name: "New OAuth app" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Google" } });
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "google" } });
    fireEvent.change(screen.getByLabelText("Client ID"), { target: { value: "cid-123" } });
    fireEvent.change(screen.getByLabelText("Scopes (comma-separated)"), { target: { value: "openid, email" } });
    fireEvent.click(screen.getByRole("button", { name: "Create OAuth app" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ provider: "google", client_id: "cid-123", scopes: ["openid", "email"] }));
  });
});
