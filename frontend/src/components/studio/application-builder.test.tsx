import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Application } from "@/lib/studio/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Leads", slug: "leads" }, { id: "e2", name: "Deals", slug: "deals" }] }) }));
vi.mock("@/lib/permissions/hooks", () => ({ useRoles: () => ({ data: [{ id: "r1", name: "Sales" }] }) }));

const appsQ = { isLoading: false, isError: false, data: { results: [] as Application[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const publish = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/studio/hooks", () => ({
  useApplications: () => appsQ,
  useCreateApp: () => create,
  useUpdateApp: () => update,
  useDeleteApp: () => del,
  usePublishApp: () => publish,
  useNavigations: () => ({ data: { results: [] } }),
  useHomeLayouts: () => ({ data: { results: [] } }),
}));

import { ApplicationBuilder } from "./application-builder";

const app = (over: Partial<Application> = {}): Application => ({
  id: "a1", name: "Sales", slug: "sales", description: "", icon: "", color: "",
  included_entity_ids: ["e1"], navigation_id: null, home_layout_id: null, role_ids: [],
  theme_overrides: {}, order: 0, is_published: false, is_active: true, created_by: null,
  created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  appsQ.data = { results: [], count: 0 };
  for (const m of [create, update, del, publish]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ApplicationBuilder", () => {
  it("creates an application with selected entities", async () => {
    render(<ApplicationBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New application" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Sales App" } });
    // disabled until at least one entity is chosen
    expect(screen.getByRole("button", { name: "Create application" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Include Leads"));
    fireEvent.click(screen.getByRole("button", { name: "Create application" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "sales_app", name: "Sales App", included_entity_ids: ["e1"], navigation_id: null, home_layout_id: null }),
    );
  });

  it("publishes a draft application", async () => {
    appsQ.data = { results: [app()], count: 1 };
    render(<ApplicationBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Publish Sales" }));
    await waitFor(() => expect(publish.mutateAsync).toHaveBeenCalledWith("a1"));
  });

  it("hides Publish on an already-published app", () => {
    appsQ.data = { results: [app({ is_published: true })], count: 1 };
    render(<ApplicationBuilder />);
    expect(screen.queryByRole("button", { name: "Publish Sales" })).not.toBeInTheDocument();
    expect(screen.getByText("published")).toBeInTheDocument();
  });

  it("deletes an application", async () => {
    appsQ.data = { results: [app()], count: 1 };
    render(<ApplicationBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Remove application Sales" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("a1"));
  });
});
