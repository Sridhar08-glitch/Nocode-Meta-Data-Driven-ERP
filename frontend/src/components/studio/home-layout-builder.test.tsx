import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HomeLayout } from "@/lib/studio/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/permissions/hooks", () => ({ useRoles: () => ({ data: [{ id: "r1", name: "Sales" }] }) }));

const homeQ = { isLoading: false, isError: false, data: { results: [] as HomeLayout[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const publish = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/studio/hooks", () => ({
  useHomeLayouts: () => homeQ,
  useCreateHome: () => create,
  useUpdateHome: () => update,
  useDeleteHome: () => del,
  usePublishHome: () => publish,
  useApplications: () => ({ data: { results: [{ id: "a1", name: "Sales" }] } }),
}));

import { HomeLayoutBuilder } from "./home-layout-builder";

beforeEach(() => {
  homeQ.data = { results: [], count: 0 };
  for (const m of [create, update, del, publish]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("HomeLayoutBuilder", () => {
  it("creates a workspace-scope layout with a widget", async () => {
    render(<HomeLayoutBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New layout" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Default home" } });
    fireEvent.change(screen.getByLabelText("Widget 1 title"), { target: { value: "Open leads" } });
    fireEvent.click(screen.getByRole("button", { name: "Create layout" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Default home",
        scope: "workspace",
        target_id: null,
        widgets: [expect.objectContaining({ type: "metric", title: "Open leads" })],
      }),
    );
  });

  it("requires a target when scope is not workspace", async () => {
    render(<HomeLayoutBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New layout" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "App home" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Scope" }));
    fireEvent.click(await screen.findByRole("option", { name: "Application" }));
    // no application chosen yet → save disabled
    expect(screen.getByRole("button", { name: "Create layout" })).toBeDisabled();
    fireEvent.click(screen.getByRole("combobox", { name: "Application" }));
    fireEvent.click(await screen.findByRole("option", { name: "Sales" }));
    fireEvent.click(screen.getByRole("button", { name: "Create layout" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ scope: "app", target_id: "a1" }));
  });
});
