import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { FieldDef } from "@/lib/metadata/types";

const create = { mutateAsync: vi.fn(), isPending: false };
const update = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useCreateField: () => create,
  useUpdateField: () => update,
}));
const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { FieldDialog } from "./field-dialog";

function fld(over: Partial<FieldDef> = {}): FieldDef {
  return {
    id: "1",
    slug: "status",
    name: "Status",
    field_type: "text",
    description: "",
    is_promoted: true,
    column_name: "status",
    is_filterable: false,
    is_sortable: false,
    is_searchable: false,
    has_index: false,
    is_required: false,
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
  create.isPending = false;
  update.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue({});
  update.mutateAsync.mockReset().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("FieldDialog (create)", () => {
  it("auto-derives slug and creates a text field with empty config", async () => {
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "First Name" } });
    expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("first_name");
    // text type → no options / formula config branch
    expect(screen.queryByLabelText(/Options/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Formula/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "first_name", field_type: "text", config: {} }),
    );
  });
});

describe("FieldDialog (create — config branches & toggles)", () => {
  it("lets the slug be overridden and toggles required/unique/promoted", async () => {
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Owner" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "owner_id" } });
    const boxes = screen.getAllByRole("checkbox");
    boxes.forEach((b) => fireEvent.click(b)); // required, unique, real column
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: "owner_id",
        is_required: true,
        is_unique: true,
        is_promoted: false,
      }),
    );
  });

  it("builds an options config for a choice type", async () => {
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Stage" } });
    fireEvent.click(screen.getByRole("combobox", { name: /Type/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Select" }));
    fireEvent.change(screen.getByLabelText(/Options/), { target: { value: "Open, In Progress" } });
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        field_type: "select",
        config: {
          options: [
            { label: "Open", value: "open" },
            { label: "In Progress", value: "in_progress" },
          ],
        },
      }),
    );
  });

  it("builds a formula config for a formula type", async () => {
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Total" } });
    fireEvent.click(screen.getByRole("combobox", { name: /Type/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Formula" }));
    fireEvent.change(screen.getByLabelText(/Formula/), { target: { value: "qty * price" } });
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ field_type: "formula", config: { expression: "qty * price" } }),
    );
  });

  it("flags an invalid slug and disables Add field", () => {
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Name" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "1bad" } });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add field" })).toBeDisabled();
  });

  it("shows a pending label while saving", () => {
    create.isPending = true;
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Name" } });
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });

  it("closes without saving on Cancel", () => {
    const onOpenChange = vi.fn();
    render(<FieldDialog entity="lead" open onOpenChange={onOpenChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(create.mutateAsync).not.toHaveBeenCalled();
  });

  it("shows an error toast when saving fails", async () => {
    create.mutateAsync.mockRejectedValueOnce(new Error("x"));
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Name" } });
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message on a typed failure", async () => {
    create.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "bad field" }));
    render(<FieldDialog entity="lead" open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Name" } });
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("bad field"));
  });
});

describe("FieldDialog (edit branches)", () => {
  it("renders the options config for a choice type, prefilled from config", () => {
    render(
      <FieldDialog
        entity="lead"
        open
        onOpenChange={vi.fn()}
        field={fld({
          field_type: "select",
          config: { options: [{ label: "Open", value: "open" }, { label: "Closed", value: "closed" }] },
        })}
      />,
    );
    const opts = screen.getByLabelText(/Options/) as HTMLInputElement;
    expect(opts.value).toBe("Open, Closed");
  });

  it("renders the formula config for a formula type, prefilled from expression", () => {
    render(
      <FieldDialog
        entity="lead"
        open
        onOpenChange={vi.fn()}
        field={fld({ field_type: "formula", config: { expression: "amount * 1.2" } })}
      />,
    );
    expect((screen.getByLabelText(/Formula/) as HTMLInputElement).value).toBe("amount * 1.2");
  });

  it("updates an existing field via the update mutation", async () => {
    const onOpenChange = vi.fn();
    render(<FieldDialog entity="lead" open onOpenChange={onOpenChange} field={fld()} />);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Stage" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ fieldSlug: "status", data: expect.objectContaining({ name: "Stage" }) }),
    );
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
