import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { CARDINALITY_OPTIONS, ON_DELETE_OPTIONS, type RelationshipDef } from "@/lib/relationships/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const entitiesQ = {
  data: [
    { id: "e1", name: "Lead" },
    { id: "e2", name: "Account" },
  ],
};
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => entitiesQ }));

const relsQ = { isLoading: false, isError: false, data: [] as RelationshipDef[] };
const del = { mutateAsync: vi.fn(), isPending: false };
const create = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/relationships/hooks", () => ({
  useRelationships: () => relsQ,
  useDeleteRelationship: () => del,
  useCreateRelationship: () => create,
}));

import { RelationshipsPanel } from "./relationships-panel";

function rel(over: Partial<RelationshipDef> = {}): RelationshipDef {
  return {
    id: "r1",
    name: "lead_account",
    slug: "lead_account",
    source_entity_id: "e1",
    target_entity_id: "e2",
    cardinality: "one_to_many",
    on_delete: "detach",
    source_field_slug: null,
    target_field_slug: null,
    junction_table: null,
    is_system: false,
    ...over,
  };
}

beforeEach(() => {
  relsQ.isLoading = false;
  relsQ.isError = false;
  relsQ.data = [];
  del.isPending = false;
  create.isPending = false;
  del.mutateAsync.mockReset().mockResolvedValue(null);
  create.mutateAsync.mockReset().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("RelationshipsPanel", () => {
  it("renders a loading skeleton", () => {
    relsQ.isLoading = true;
    const { container } = render(<RelationshipsPanel entityId="e1" />);
    expect(container.querySelector(".h-48")).toBeTruthy();
  });

  it("renders an error state", () => {
    relsQ.isError = true;
    render(<RelationshipsPanel entityId="e1" />);
    expect(screen.getByText("Couldn't load relationships")).toBeInTheDocument();
  });

  it("shows an empty state and opens the create dialog", () => {
    render(<RelationshipsPanel entityId="e1" />);
    expect(screen.getByText("No relationships")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("opens the create dialog from the empty-state action", () => {
    render(<RelationshipsPanel entityId="e1" />);
    const actions = screen.getAllByRole("button", { name: "New relationship" });
    fireEvent.click(actions[actions.length - 1]); // EmptyState action button
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("lists relationships touching this entity with a cardinality glyph", () => {
    relsQ.data = [rel(), rel({ id: "r2", source_entity_id: "e9", target_entity_id: "e8" })];
    render(<RelationshipsPanel entityId="e1" />);
    // only r1 touches e1
    expect(screen.getByText("1 relationship")).toBeInTheDocument();
    expect(screen.getByText("Lead")).toBeInTheDocument();
    expect(screen.getByText("Account")).toBeInTheDocument();
    expect(screen.getByLabelText("one_to_many")).toHaveTextContent("1—∞");
  });

  it("pluralises the count and resolves unknown entities to '?'", () => {
    relsQ.data = [rel({ target_entity_id: "missing" }), rel({ id: "r2" })];
    render(<RelationshipsPanel entityId="e1" />);
    expect(screen.getByText("2 relationships")).toBeInTheDocument();
    expect(screen.getAllByText("?").length).toBeGreaterThanOrEqual(1);
  });

  it("deletes a relationship", async () => {
    relsQ.data = [rel()];
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("r1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces a delete error", async () => {
    del.mutateAsync.mockRejectedValueOnce(new Error("x"));
    relsQ.data = [rel()];
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("disables delete for a system relationship", () => {
    relsQ.data = [rel({ is_system: true })];
    render(<RelationshipsPanel entityId="e1" />);
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });

  it("uses the ApiError message on a typed delete failure", async () => {
    del.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "constraint" }));
    relsQ.data = [rel()];
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("constraint"));
  });
});

describe("RelationshipCreateDialog", () => {
  it("keeps Create disabled until a name and target are set", () => {
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Owner" } });
    // still no target → disabled
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  it("creates a relationship with chosen target, cardinality and on-delete", async () => {
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Owner" } });

    // Target entity → Account
    fireEvent.click(screen.getByRole("combobox", { name: /Target entity/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Account" }));

    // Cardinality → Many-to-many
    fireEvent.click(screen.getByRole("combobox", { name: /Cardinality/i }));
    fireEvent.click(await screen.findByRole("option", { name: CARDINALITY_OPTIONS[2].label }));

    // On delete → second option
    fireEvent.click(screen.getByRole("combobox", { name: /On delete/i }));
    fireEvent.click(await screen.findByRole("option", { name: ON_DELETE_OPTIONS[1].label }));

    const createBtn = screen.getByRole("button", { name: "Create" });
    await waitFor(() => expect(createBtn).toBeEnabled());
    fireEvent.click(createBtn);
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Owner",
        slug: "owner",
        source_entity_id: "e1",
        target_entity_id: "e2",
        cardinality: CARDINALITY_OPTIONS[2].value,
        on_delete: ON_DELETE_OPTIONS[1].value,
      }),
    );
  });

  it("surfaces a create error", async () => {
    create.mutateAsync.mockRejectedValueOnce(new Error("x"));
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Owner" } });
    fireEvent.click(screen.getByRole("combobox", { name: /Target entity/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Account" }));
    const createBtn = screen.getByRole("button", { name: "Create" });
    await waitFor(() => expect(createBtn).toBeEnabled());
    fireEvent.click(createBtn);
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message on a typed create failure", async () => {
    create.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "dup slug" }));
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Owner" } });
    fireEvent.click(screen.getByRole("combobox", { name: /Target entity/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Account" }));
    const createBtn = screen.getByRole("button", { name: "Create" });
    await waitFor(() => expect(createBtn).toBeEnabled());
    fireEvent.click(createBtn);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("dup slug"));
  });

  it("closes the create dialog on Cancel", () => {
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(create.mutateAsync).not.toHaveBeenCalled();
  });

  it("shows a pending label and tolerates no entity list", () => {
    create.isPending = true;
    entitiesQ.data = undefined as unknown as typeof entitiesQ.data;
    render(<RelationshipsPanel entityId="e1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "New relationship" })[0]);
    expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
    entitiesQ.data = [
      { id: "e1", name: "Lead" },
      { id: "e2", name: "Account" },
    ];
  });
});
