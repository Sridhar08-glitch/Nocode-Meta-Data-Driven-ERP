import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { FieldDef, FormDefinition } from "@/lib/metadata/types";

const create = { mutateAsync: vi.fn(), isPending: false };
const update = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useCreateForm: () => create,
  useUpdateForm: () => update,
}));
const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { FormBuilder } from "./form-builder";

function fld(slug: string, name: string, field_type = "text"): FieldDef {
  return {
    id: slug,
    slug,
    name,
    field_type,
    description: "",
    is_promoted: true,
    column_name: slug,
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
  };
}

const fields = [fld("name", "Name"), fld("email", "Email", "email"), fld("phone", "Phone", "phone")];
const form: FormDefinition = {
  id: "form-1",
  entity: "e1",
  entity_slug: "lead",
  name: "Intake",
  is_default: true,
  is_public: false,
  layout: [{ key: "main", title: "Details", columns: 1, fields: ["name", "email"], condition: null }],
  settings: { layout_type: "sections" },
};

function setup() {
  return render(
    <FormBuilder entity="lead" entityName="Lead" fields={fields} form={form} onSaved={onSaved} />,
  );
}
const onSaved = vi.fn();

beforeEach(() => {
  create.isPending = false;
  update.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue(form);
  update.mutateAsync.mockReset().mockResolvedValue(form);
  vi.clearAllMocks();
});

describe("FormBuilder", () => {
  it("renders a live preview of the placed fields", () => {
    setup();
    // Each placed field label appears both in the section list and the rendered preview.
    expect(screen.getAllByText("Name").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Email").length).toBeGreaterThanOrEqual(2);
  });

  it("exposes correctly-disabled move controls for the first/last field", () => {
    setup();
    expect(screen.getByRole("button", { name: "Move name up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move name down" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Move email down" })).toBeDisabled();
  });

  it("adds a section", () => {
    setup();
    expect(screen.getByLabelText("Section 1 title")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));
    expect(screen.getByLabelText("Section 2 title")).toBeInTheDocument();
  });

  it("removes a field from its section", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Remove name" }));
    // the section list no longer offers a move control for name
    expect(screen.queryByRole("button", { name: "Move name down" })).not.toBeInTheDocument();
  });

  it("saves an existing form via the update mutation", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Save form" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ formId: "form-1", data: expect.objectContaining({ name: "Intake" }) }),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("moving the first field down reorders the section list", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Move name down" }));
    // after the swap order is [email, name]: name is last (down disabled), name's up is enabled
    expect(screen.getByRole("button", { name: "Move name down" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move name up" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Move email up" })).toBeDisabled();
  });

  it("edits the section title", () => {
    setup();
    const title = screen.getByLabelText("Section 1 title") as HTMLInputElement;
    fireEvent.change(title, { target: { value: "Contact" } });
    expect(title.value).toBe("Contact");
  });

  it("changes the section column count", async () => {
    setup();
    fireEvent.click(screen.getByRole("combobox", { name: "Columns" }));
    fireEvent.click(await screen.findByRole("option", { name: "2 cols" }));
    expect(screen.getByRole("combobox", { name: "Columns" })).toHaveTextContent("2 cols");
  });

  it("switches the layout type", async () => {
    setup();
    fireEvent.click(screen.getByRole("combobox", { name: "Layout" }));
    fireEvent.click(await screen.findByRole("option", { name: "Wizard" }));
    expect(screen.getByRole("combobox", { name: "Layout" })).toHaveTextContent("Wizard");
  });

  it("adds an unplaced field to a section", async () => {
    setup();
    fireEvent.click(screen.getByRole("combobox", { name: /Add field to Details/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Phone" }));
    expect(screen.getByRole("button", { name: "Move phone down" })).toBeInTheDocument();
  });

  it("removes a section", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));
    expect(screen.getByLabelText("Section 2 title")).toBeInTheDocument();
    const removes = screen.getAllByRole("button", { name: "Remove section" });
    fireEvent.click(removes[removes.length - 1]);
    expect(screen.queryByLabelText("Section 2 title")).not.toBeInTheDocument();
  });

  it("moves a section up", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));
    const ups = screen.getAllByRole("button", { name: "Move section up" });
    expect(ups[0]).toBeDisabled();
    expect(ups[1]).toBeEnabled();
    fireEvent.click(ups[1]); // promote section 2 → now the new section is first
    expect(screen.getByLabelText("Section 1 title")).toHaveValue("Section 2");
  });

  it("shows a pending label while saving", () => {
    update.isPending = true;
    setup();
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });

  it("edits the form name", () => {
    setup();
    const nameInput = screen.getByLabelText("Form name") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Renamed" } });
    expect(nameInput.value).toBe("Renamed");
  });

  it("moves a field up", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Move email up" }));
    // order is now [email, name]
    expect(screen.getByRole("button", { name: "Move email up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move name down" })).toBeDisabled();
  });

  it("moves a section down", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));
    const downs = screen.getAllByRole("button", { name: "Move section down" });
    expect(downs[0]).toBeEnabled();
    fireEvent.click(downs[0]); // demote section 1 → "Details" becomes second
    expect(screen.getByLabelText("Section 2 title")).toHaveValue("Details");
  });

  it("creates a new form when none exists", async () => {
    render(<FormBuilder entity="lead" entityName="Lead" fields={fields} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Save form" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ is_default: true, name: "Default" }),
    );
  });

  it("shows an error toast when saving fails", async () => {
    update.mutateAsync.mockRejectedValueOnce(new Error("x"));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Save form" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message on a typed save failure", async () => {
    update.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "bad layout" }));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Save form" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("bad layout"));
  });

  it("the disabled preview form swallows submit without saving", () => {
    const { container } = setup();
    const previewForm = container.querySelector("form");
    expect(previewForm).toBeTruthy();
    fireEvent.submit(previewForm!);
    // preview submit is a no-op — never triggers a form save
    expect(create.mutateAsync).not.toHaveBeenCalled();
    expect(update.mutateAsync).not.toHaveBeenCalled();
  });
});
