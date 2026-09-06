import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PublicFormSchema } from "@/lib/public-forms/api";

const schemaQ = { isLoading: false, isError: false, data: undefined as PublicFormSchema | undefined };
const submit = { mutateAsync: vi.fn(() => Promise.resolve({ success: true })), isPending: false };
vi.mock("@/lib/public-forms/hooks", () => ({
  usePublicFormSchema: () => schemaQ,
  useSubmitPublicForm: () => submit,
}));

import { PublicFormRuntime } from "./public-form-runtime";

function field(slug: string, name: string, over = {}) {
  return {
    slug, name, field_type: "text", description: "", is_required: false, is_unique: false,
    is_hidden: false, is_readonly: false, is_system: false, default_value: null,
    validation_rules: [], config: {}, order: 0, read_roles: [], write_roles: [], ...over,
  };
}

const schema: PublicFormSchema = {
  form_id: "f1", name: "Contact us", entity_slug: "lead", honeypot_field: "_hp", settings: { submit_text: "Send" },
  schema: {
    entity_slug: "lead", entity_name: "Lead", form_id: "f1", form_name: "Contact us", layout_type: "single",
    sections: [{ key: "main", title: "", columns: 1, fields: ["name", "message"], condition: null }],
    fields: [field("name", "Name", { is_required: true }), field("message", "Message", { field_type: "long_text" })],
    conditional_rules: [],
  },
};

beforeEach(() => {
  schemaQ.data = schema;
  submit.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("PublicFormRuntime", () => {
  it("renders the public fields", () => {
    render(<PublicFormRuntime formId="f1" />);
    expect(screen.getByRole("heading", { name: "Contact us" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Message/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("blocks submit when a required field is empty", async () => {
    render(<PublicFormRuntime formId="f1" />);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(/required fields/)).toBeInTheDocument();
    expect(submit.mutateAsync).not.toHaveBeenCalled();
  });

  it("submits values + honeypot and shows a thank-you", async () => {
    render(<PublicFormRuntime formId="f1" />);
    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(submit.mutateAsync).toHaveBeenCalled());
    expect(submit.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ name: "Ada", message: "Hello", _hp: "" }));
    expect(await screen.findByText("Thank you")).toBeInTheDocument();
  });
});
