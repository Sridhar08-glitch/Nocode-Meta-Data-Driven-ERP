import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FormField } from "@/lib/metadata/types";

import { BooleanField } from "./boolean-field";
import { optionList, type FieldProps } from "./field-props";
import {
  DateField,
  FileField,
  JsonField,
  NumberInputField,
  ReadOnlyField,
  TextareaField,
  TextInputField,
} from "./inputs";
import { SelectField } from "./select-field";

function fld(over: Partial<FormField> = {}): FormField {
  return {
    slug: "f",
    name: "F",
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

function props(over: Partial<FieldProps> = {}): FieldProps {
  return {
    field: fld(),
    id: "field-f",
    value: "",
    onChange: vi.fn(),
    onBlur: vi.fn(),
    ...over,
  };
}

describe("input field components", () => {
  it("TextInputField maps field_type to input type and emits changes", () => {
    const onChange = vi.fn();
    render(<TextInputField {...props({ field: fld({ field_type: "email" }), onChange })} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.type).toBe("email");
    fireEvent.change(input, { target: { value: "a@b.com" } });
    expect(onChange).toHaveBeenCalledWith("a@b.com");
  });

  it("NumberInputField shows empty for null and emits raw value", () => {
    const onChange = vi.fn();
    render(<NumberInputField {...props({ field: fld({ field_type: "integer" }), value: null, onChange })} />);
    const input = screen.getByRole("spinbutton") as HTMLInputElement;
    expect(input.value).toBe("");
    fireEvent.change(input, { target: { value: "7" } });
    expect(onChange).toHaveBeenCalledWith("7");
  });

  it("DateField uses the right input type per field_type", () => {
    const { rerender } = render(<DateField {...props({ field: fld({ field_type: "date" }) })} />);
    expect((document.getElementById("field-f") as HTMLInputElement).type).toBe("date");
    rerender(<DateField {...props({ field: fld({ field_type: "datetime" }) })} />);
    expect((document.getElementById("field-f") as HTMLInputElement).type).toBe("datetime-local");
    rerender(<DateField {...props({ field: fld({ field_type: "time" }) })} />);
    expect((document.getElementById("field-f") as HTMLInputElement).type).toBe("time");
  });

  it("TextareaField renders a textarea and emits changes", () => {
    const onChange = vi.fn();
    render(<TextareaField {...props({ field: fld({ field_type: "textarea" }), onChange })} />);
    const ta = screen.getByRole("textbox");
    expect(ta.tagName.toLowerCase()).toBe("textarea");
    fireEvent.change(ta, { target: { value: "notes" } });
    expect(onChange).toHaveBeenCalledWith("notes");
  });

  it("JsonField passes a string value through unchanged", () => {
    render(<JsonField {...props({ field: fld({ field_type: "json" }), value: '{"raw":1}' })} />);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe('{"raw":1}');
  });

  it("JsonField stringifies an object value", () => {
    render(<JsonField {...props({ field: fld({ field_type: "json" }), value: { a: 1 } })} />);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toContain('"a": 1');
  });

  it("FileField emits the file name, or '' when cleared", () => {
    const onChange = vi.fn();
    render(<FileField {...props({ field: fld({ field_type: "file" }), onChange })} />);
    const input = document.getElementById("field-f") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "doc.pdf")] } });
    expect(onChange).toHaveBeenCalledWith("doc.pdf");
    fireEvent.change(input, { target: { files: [] } });
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("ReadOnlyField formats the value and shows a dash when empty", () => {
    const { rerender } = render(
      <ReadOnlyField {...props({ field: fld({ field_type: "boolean" }), value: true })} />,
    );
    expect(screen.getByText("Yes").tagName.toLowerCase()).toBe("output");
    rerender(<ReadOnlyField {...props({ field: fld({ field_type: "text" }), value: "" })} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("BooleanField reflects + toggles", () => {
    const onChange = vi.fn();
    render(<BooleanField {...props({ field: fld({ field_type: "boolean" }), value: false, onChange })} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("SelectField renders its options", () => {
    render(
      <SelectField
        {...props({
          field: fld({ field_type: "select", config: { options: [{ value: "a", label: "Alpha" }] } }),
        })}
      />,
    );
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});

describe("optionList", () => {
  it("normalises object, string, and id/value option shapes", () => {
    expect(optionList(fld({ config: { options: [{ value: "a", label: "A" }] } }))).toEqual([
      { value: "a", label: "A" },
    ]);
    expect(optionList(fld({ config: { options: ["x"] } }))).toEqual([{ value: "x", label: "x" }]);
    expect(optionList(fld({ config: { options: [{ id: "i", value: "v" }] } }))[0].value).toBe("v");
    expect(optionList(fld())).toEqual([]);
  });
});
