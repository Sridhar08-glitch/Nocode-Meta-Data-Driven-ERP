import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SortClause } from "@/lib/nql/types";
import type { SavedView } from "@/lib/saved-views/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const viewsQ = { data: { results: [] as SavedView[], count: 0 } };
const create = { mutateAsync: vi.fn(), isPending: false };
const update = { mutateAsync: vi.fn(), isPending: false };
const del = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/saved-views/hooks", () => ({
  useSavedViews: () => viewsQ,
  useCreateSavedView: () => create,
  useUpdateSavedView: () => update,
  useDeleteSavedView: () => del,
}));

import { SavedViewsBar } from "./saved-views-bar";

function view(over: Partial<SavedView> = {}): SavedView {
  return {
    id: "v1",
    entity_id: "e1",
    name: "Open deals",
    hidden_field_slugs: [],
    column_widths: {},
    personal_filters: [],
    sort_overrides: [{ field: "value", direction: "desc" }],
    group_by_override: "",
    is_pinned: false,
    ...over,
  };
}

const sort: SortClause = { field: "name", direction: "asc" };

beforeEach(() => {
  viewsQ.data = { results: [], count: 0 };
  create.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue({ id: "v2" });
  update.mutateAsync.mockReset().mockResolvedValue({});
  del.mutateAsync.mockReset().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("SavedViewsBar", () => {
  it("saves the current sort as a new view with the typed name", async () => {
    render(<SavedViewsBar entitySlug="deals" sort={sort} onApply={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled(); // gated on name
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "My deals" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith({
        entity_slug: "deals",
        name: "My deals",
        sort_overrides: [{ field: "name", direction: "asc" }],
      }),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("saves an empty sort_overrides when there is no active sort", async () => {
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "All" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith({
        entity_slug: "deals",
        name: "All",
        sort_overrides: [],
      }),
    );
  });

  it("applies a saved view's sort via the callback when loaded", () => {
    viewsQ.data = { results: [view()], count: 1 };
    const onApply = vi.fn();
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={onApply} />);
    fireEvent.click(screen.getByRole("button", { name: "Open deals" }));
    expect(onApply).toHaveBeenCalledWith({ field: "value", direction: "desc" });
    expect(toast.info).toHaveBeenCalled();
  });

  it("applies null when a loaded view has no sort override", () => {
    viewsQ.data = { results: [view({ name: "Plain", sort_overrides: [] })], count: 1 };
    const onApply = vi.fn();
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={onApply} />);
    fireEvent.click(screen.getByRole("button", { name: "Plain" }));
    expect(onApply).toHaveBeenCalledWith(null);
  });

  it("toggles the pin state with the inverted value", async () => {
    viewsQ.data = { results: [view({ is_pinned: false })], count: 1 };
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Pin Open deals" }));
    await waitFor(() =>
      expect(update.mutateAsync).toHaveBeenCalledWith({ id: "v1", data: { is_pinned: true } }),
    );
  });

  it("deletes a view and toasts", async () => {
    viewsQ.data = { results: [view()], count: 1 };
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete Open deals" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("v1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces errors from pin and delete", async () => {
    update.mutateAsync.mockRejectedValueOnce(new Error("x"));
    del.mutateAsync.mockRejectedValueOnce(new Error("y"));
    viewsQ.data = { results: [view()], count: 1 };
    render(<SavedViewsBar entitySlug="deals" sort={null} onApply={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Pin Open deals" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Delete Open deals" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(2));
  });
});
