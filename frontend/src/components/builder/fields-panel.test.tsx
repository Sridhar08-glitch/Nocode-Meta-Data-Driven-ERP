import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { FieldDef } from "@/lib/metadata/types";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

// Impact dialog (opens before delete) fetches references — return none by default.
const fieldImpact = vi.hoisted(() => vi.fn(() => Promise.resolve({ dependents: [], count: 0 })));
vi.mock("@/lib/metadata/builder-api", () => ({ builderApi: { fieldImpact } }));

function render2(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

/** Open the impact-warning dialog, wait for the impact check to resolve, then confirm the delete. */
async function confirmDelete(fieldName: string) {
  fireEvent.click(screen.getByRole("button", { name: `Delete ${fieldName}` }));
  await screen.findByText(/No known references/); // impact resolved (count 0) → confirm enabled
  fireEvent.click(screen.getByRole("button", { name: "Delete anyway" }));
}

const fieldsQ = { isLoading: false, isError: false, data: [] as FieldDef[] };
const del = { mutateAsync: vi.fn(), isPending: false };
const promote = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useFields: () => fieldsQ,
  useDeleteField: () => del,
  usePromoteField: () => promote,
  // FieldDialog (rendered as a child) consumes these:
  useCreateField: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateField: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { FieldsPanel } from "./fields-panel";

function fld(over: Partial<FieldDef> = {}): FieldDef {
  return {
    id: over.slug ?? "name",
    slug: "name",
    name: "Name",
    field_type: "text",
    description: "",
    is_promoted: true,
    column_name: "name",
    is_filterable: false,
    is_sortable: false,
    is_searchable: false,
    has_index: false,
    is_required: true,
    is_unique: false,
    default_value: null,
    is_system: false,
    is_hidden: false,
    is_readonly: false,
    order: 0,
    config: {},
    read_roles: [],
    write_roles: [],
    ...over,
  };
}

beforeEach(() => {
  fieldsQ.isLoading = false;
  fieldsQ.isError = false;
  fieldsQ.data = [];
  del.isPending = false;
  promote.isPending = false;
  del.mutateAsync.mockReset().mockResolvedValue(null);
  promote.mutateAsync.mockReset().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("FieldsPanel", () => {
  it("renders a loading skeleton", () => {
    fieldsQ.isLoading = true;
    const { container } = render(<FieldsPanel entity="lead" />);
    expect(container.querySelector(".h-64")).toBeTruthy();
  });

  it("renders an error state", () => {
    fieldsQ.isError = true;
    render(<FieldsPanel entity="lead" />);
    expect(screen.getByText("Couldn't load fields")).toBeInTheDocument();
  });

  it("shows an empty state and opens the create dialog", () => {
    render(<FieldsPanel entity="lead" />);
    expect(screen.getByText("No fields yet")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Add field" })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("lists fields with flags and offers promote/edit/delete", () => {
    fieldsQ.data = [
      fld(),
      fld({ slug: "ext_id", name: "External", is_system: true, is_promoted: false, is_required: false }),
    ];
    render(<FieldsPanel entity="lead" />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("required")).toBeInTheDocument();
    expect(screen.getByText("column")).toBeInTheDocument();
    expect(screen.getByText("virtual")).toBeInTheDocument();
    // system field hides promote + delete (only Edit remains)
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^Delete / })).toHaveLength(1);
  });

  it("renders unique badge, raw unknown types, and a Promote action", () => {
    fieldsQ.data = [
      fld({ slug: "code", name: "Code", is_unique: true, is_required: false }),
      fld({ slug: "weird", name: "Weird", field_type: "exotic_type", is_promoted: false, is_required: false }),
    ];
    render(<FieldsPanel entity="lead" />);
    expect(screen.getByText("unique")).toBeInTheDocument();
    expect(screen.getByText("exotic_type")).toBeInTheDocument(); // unknown type → raw slug
    expect(screen.getByRole("button", { name: "Promote" })).toBeInTheDocument();
  });

  it("treats undefined data as empty", () => {
    fieldsQ.data = undefined as unknown as FieldDef[];
    render(<FieldsPanel entity="lead" />);
    expect(screen.getByText("No fields yet")).toBeInTheDocument();
  });

  it("toggles promotion", async () => {
    fieldsQ.data = [fld()];
    render(<FieldsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Demote" }));
    await waitFor(() =>
      expect(promote.mutateAsync).toHaveBeenCalledWith({ fieldSlug: "name", promote: false }),
    );
  });

  it("deletes a field (after the impact check) with a success toast", async () => {
    fieldsQ.data = [fld()];
    render2(<FieldsPanel entity="lead" />);
    await confirmDelete("Name");
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("name"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces a delete error", async () => {
    del.mutateAsync.mockRejectedValueOnce(new Error("nope"));
    fieldsQ.data = [fld()];
    render2(<FieldsPanel entity="lead" />);
    await confirmDelete("Name");
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("surfaces a promote error", async () => {
    promote.mutateAsync.mockRejectedValueOnce(new Error("nope"));
    fieldsQ.data = [fld()];
    render(<FieldsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Demote" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message on delete and promote failures", async () => {
    del.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "in use" }));
    promote.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "cannot demote" }));
    fieldsQ.data = [fld()];
    render2(<FieldsPanel entity="lead" />);
    await confirmDelete("Name");
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("in use"));
    fireEvent.click(screen.getByRole("button", { name: "Demote" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("cannot demote"));
  });

  it("opens the create dialog from the empty-state action", () => {
    render(<FieldsPanel entity="lead" />);
    const actions = screen.getAllByRole("button", { name: "Add field" });
    fireEvent.click(actions[actions.length - 1]); // the EmptyState action button
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("opens and closes the edit dialog for a field", () => {
    fieldsQ.data = [fld()];
    render(<FieldsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
