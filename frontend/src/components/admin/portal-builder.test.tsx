import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PortalConfig, PortalGrant, PortalUser } from "@/lib/portal-admin/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Tickets", slug: "ticket" }] }) }));

const cfg: PortalConfig = {
  id: "c1", is_enabled: false, name: "Portal", custom_domain: "", logo_url: "", primary_color: "",
  exposed_entity_ids: [], default_role_id: null, allow_self_signup: false, signup_domain_whitelist: [], welcome_message: "",
};
const configQ = { isLoading: false, isError: false, data: cfg };
const usersQ = { isLoading: false, isError: false, data: { results: [] as PortalUser[], count: 0 } };
const grantsQ = { isLoading: false, isError: false, data: { results: [] as PortalGrant[], count: 0 } };
const updateCfg = { mutateAsync: vi.fn(() => Promise.resolve(cfg)), isPending: false };
const createUser = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delUser = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const createGrant = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delGrant = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/portal-admin/hooks", () => ({
  usePortalConfig: () => configQ,
  useUpdatePortalConfig: () => updateCfg,
  usePortalUsers: () => usersQ,
  useCreatePortalUser: () => createUser,
  useDeletePortalUser: () => delUser,
  usePortalGrants: () => grantsQ,
  useCreatePortalGrant: () => createGrant,
  useDeletePortalGrant: () => delGrant,
}));

import { PortalBuilder } from "./portal-builder";

beforeEach(() => {
  usersQ.data = { results: [], count: 0 };
  grantsQ.data = { results: [], count: 0 };
  for (const m of [updateCfg, createUser, delUser, createGrant, delGrant]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("PortalBuilder", () => {
  it("saves config with exposed entities", async () => {
    render(<PortalBuilder />);
    fireEvent.click(screen.getByLabelText("Expose Tickets"));
    fireEvent.click(screen.getByRole("button", { name: "Save config" }));
    await waitFor(() => expect(updateCfg.mutateAsync).toHaveBeenCalled());
    expect(updateCfg.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ exposed_entity_ids: ["e1"] }));
  });

  it("creates a portal user with a linked record", async () => {
    render(<PortalBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "New portal user" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "client@acme.com" } });
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Client One" } });
    fireEvent.change(screen.getByLabelText("Password (min 8)"), { target: { value: "portalPW123" } });
    fireEvent.change(screen.getByLabelText("Linked record ID (row scope)"), { target: { value: "rec-7" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));
    await waitFor(() => expect(createUser.mutateAsync).toHaveBeenCalled());
    expect(createUser.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ email: "client@acme.com", linked_record_id: "rec-7", portal_type: "customer" }));
  });

  it("creates an entity grant with a link field", async () => {
    render(<PortalBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "New grant" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Tickets" }));
    fireEvent.change(screen.getByLabelText("Link field"), { target: { value: "customer" } });
    fireEvent.click(screen.getByRole("button", { name: "Create grant" }));
    await waitFor(() => expect(createGrant.mutateAsync).toHaveBeenCalled());
    expect(createGrant.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ entity_slug: "ticket", link_field: "customer", can_read: true }));
  });
});
