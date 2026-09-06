import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RelationLoaderProvider, type RelationLoader } from "@/components/fields/relation-field";
import type { FormField, FormSchema } from "@/lib/metadata/types";

import { FormRenderer } from "./FormRenderer";

function field(slug: string, over: Partial<FormField> = {}): FormField {
  return {
    slug,
    name: over.name ?? slug,
    field_type: "text",
    description: "",
    is_required: false,
    is_unique: false,
    is_hidden: false,
    is_readonly: false,
    is_system: false,
    default_value: null,
    validation_rules: [],
    config: {},
    order: 0,
    read_roles: [],
    write_roles: [],
    ...over,
  };
}

function schema(fields: FormField[], over: Partial<FormSchema> = {}): FormSchema {
  return {
    entity_slug: "lead",
    entity_name: "Lead",
    form_id: null,
    form_name: "Default",
    layout_type: "sections",
    sections: [{ key: "main", title: "Details", columns: 1, fields: fields.map((f) => f.slug), condition: null }],
    fields,
    conditional_rules: [],
    ...over,
  };
}

const stubLoader: RelationLoader = async () => [
  { value: "1", label: "Acme" },
  { value: "2", label: "Globex" },
];

function renderForm(s: FormSchema, onSubmit = vi.fn(), initialValues?: Record<string, unknown>) {
  render(
    <RelationLoaderProvider loader={stubLoader}>
      <FormRenderer schema={s} onSubmit={onSubmit} initialValues={initialValues} />
    </RelationLoaderProvider>,
  );
  return onSubmit;
}

describe("FormRenderer", () => {
  it("submits valid values", async () => {
    const onSubmit = renderForm(schema([field("name", { name: "Name" })]));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ name: "Acme" }));
  });

  it("blocks submit and shows an error for a required field", async () => {
    const onSubmit = renderForm(schema([field("name", { name: "Name", is_required: true })]));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("required");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("marks required fields with an asterisk", () => {
    renderForm(schema([field("name", { name: "Name", is_required: true })]));
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByText("*")).toBeInTheDocument();
  });

  it("renders read-only (computed) fields as output, not inputs", () => {
    renderForm(
      schema([field("total", { name: "Total", field_type: "formula" })]),
      vi.fn(),
      { total: 42 },
    );
    const out = screen.getByText("42");
    expect(out.tagName.toLowerCase()).toBe("output");
  });

  it("renders a control for every field kind", () => {
    renderForm(
      schema([
        field("txt", { name: "Txt", field_type: "text" }),
        field("num", { name: "Num", field_type: "integer" }),
        field("on", { name: "On", field_type: "boolean" }),
        field("sel", { name: "Sel", field_type: "select", config: { options: ["a", "b"] } }),
        field("multi", { name: "Multi", field_type: "multi_select", config: { options: ["a", "b"] } }),
        field("day", { name: "Day", field_type: "date" }),
        field("blob", { name: "Blob", field_type: "json" }),
        field("doc", { name: "Doc", field_type: "file" }),
        field("rel", { name: "Rel", field_type: "lookup", config: { target_entity_slug: "company" } }),
      ]),
    );
    expect((screen.getByLabelText("Num") as HTMLInputElement).type).toBe("number");
    expect((screen.getByLabelText("Day") as HTMLInputElement).type).toBe("date");
    expect(screen.getByRole("switch")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Multi" })).toBeInTheDocument();
    expect(screen.getByLabelText("Rel")).toBeInTheDocument();
  });

  it("toggles a boolean field", async () => {
    const onSubmit = renderForm(schema([field("active", { name: "Active", field_type: "boolean" })]));
    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ active: true }));
  });

  it("checks a multi-select option", async () => {
    const onSubmit = renderForm(
      schema([field("tags", { name: "Tags", field_type: "multi_select", config: { options: ["a", "b"] } })]),
    );
    const group = screen.getByRole("group", { name: "Tags" });
    fireEvent.click(within(group).getAllByRole("checkbox")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ tags: ["a"] }));
  });

  it("searches and selects a relation via the injected loader", async () => {
    const onSubmit = renderForm(
      schema([field("company", { name: "Company", field_type: "lookup", config: { target_entity_slug: "company" } })]),
    );
    fireEvent.click(screen.getByLabelText("Company"));
    fireEvent.click(await screen.findByRole("button", { name: /Acme/ }));
    expect(await screen.findByText("Acme")).toBeInTheDocument(); // badge
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ company: "1" }));
  });

  describe("conditional visibility", () => {
    const condSchema = schema(
      [
        field("kind", { name: "Kind", field_type: "select", config: { options: ["person", "company"] } }),
        field("first_name", { name: "First name", is_required: true }),
      ],
      {
        conditional_rules: [
          { field: "kind", op: "=", value: "company", action: "hide", target_field: "first_name" },
        ],
      },
    );

    it("hides a field when its rule matches and ignores its validation", async () => {
      const onSubmit = renderForm(condSchema, vi.fn(), { kind: "company" });
      expect(screen.queryByLabelText("First name")).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ kind: "company" }));
    });

    it("shows + validates the field when the rule does not match", async () => {
      const onSubmit = renderForm(condSchema, vi.fn(), { kind: "person" });
      expect(screen.getByLabelText("First name")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(await screen.findByRole("alert")).toBeInTheDocument();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  describe("wizard", () => {
    const wizard = schema(
      [field("a", { name: "A", is_required: true }), field("b", { name: "B" })],
      {
        layout_type: "wizard",
        sections: [
          { key: "s1", title: "Step 1", columns: 1, fields: ["a"], condition: null },
          { key: "s2", title: "Step 2", columns: 1, fields: ["b"], condition: null },
        ],
      },
    );

    it("validates the step before advancing, then submits on the last step", async () => {
      const onSubmit = renderForm(wizard);
      // Step 1 has a required field — Next should not advance while empty.
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(await screen.findByRole("alert")).toBeInTheDocument();
      expect(screen.queryByLabelText("B")).not.toBeInTheDocument();

      fireEvent.change(screen.getByLabelText("A"), { target: { value: "x" } });
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      await waitFor(() => expect(screen.getByLabelText("B")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: "Back" }));
      expect(await screen.findByLabelText("A")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      fireEvent.click(await screen.findByRole("button", { name: "Save" }));
      await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ a: "x", b: "" }));
    });
  });
});
