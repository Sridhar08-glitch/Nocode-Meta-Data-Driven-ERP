import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Navigation } from "@/lib/studio/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Leads", slug: "leads" }] }) }));

const navQ = { isLoading: false, isError: false, data: { results: [] as Navigation[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const publish = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/studio/hooks", () => ({
  useNavigations: () => navQ,
  useCreateNav: () => create,
  useUpdateNav: () => update,
  useDeleteNav: () => del,
  usePublishNav: () => publish,
}));

import { NavigationBuilder } from "./navigation-builder";

beforeEach(() => {
  navQ.data = { results: [], count: 0 };
  for (const m of [create, update, del, publish]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("NavigationBuilder", () => {
  it("creates a menu with a group + entity item", async () => {
    render(<NavigationBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New menu" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Main menu" } });
    fireEvent.change(screen.getByLabelText("Group 1 label"), { target: { value: "CRM" } });
    fireEvent.change(screen.getByLabelText("Group 1 item 1 label"), { target: { value: "Leads" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Group 1 item 1 entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Leads" }));
    fireEvent.click(screen.getByRole("button", { name: "Create menu" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Main menu",
        scope: "workspace",
        tree: [{ label: "CRM", items: [{ label: "Leads", type: "entity", target: "leads" }] }],
      }),
    );
  });

  it("reorders groups with the move-up control", () => {
    render(<NavigationBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New menu" })[0]);
    fireEvent.change(screen.getByLabelText("Group 1 label"), { target: { value: "A" } });
    fireEvent.click(screen.getByRole("button", { name: "Add group" }));
    fireEvent.change(screen.getByLabelText("Group 2 label"), { target: { value: "B" } });
    fireEvent.click(screen.getByRole("button", { name: "Move group 2 up" }));
    expect(screen.getByLabelText("Group 1 label")).toHaveValue("B");
    expect(screen.getByLabelText("Group 2 label")).toHaveValue("A");
  });
});
