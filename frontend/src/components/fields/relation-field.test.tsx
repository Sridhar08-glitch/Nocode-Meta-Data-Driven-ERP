import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FormField } from "@/lib/metadata/types";

import type { FieldProps } from "./field-props";
import {
  RelationField,
  RelationLoaderProvider,
  defaultRelationLoader,
  type RelationLoader,
} from "./relation-field";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn() }));
import { apiGet } from "@/lib/api/request";

function fld(over: Partial<FormField> = {}): FormField {
  return {
    slug: "rel",
    name: "Rel",
    field_type: "lookup",
    description: "",
    is_required: false,
    is_unique: false,
    is_hidden: false,
    is_readonly: false,
    is_system: false,
    default_value: null,
    validation_rules: [],
    config: { target_entity_slug: "company" },
    order: 0,
    read_roles: [],
    write_roles: [],
    ...over,
  };
}

function renderRelation(over: Partial<FieldProps>, loader: RelationLoader) {
  const onChange = over.onChange ?? vi.fn();
  render(
    <RelationLoaderProvider loader={loader}>
      <RelationField
        field={over.field ?? fld()}
        id="field-rel"
        value={over.value ?? ""}
        onChange={onChange}
        onBlur={vi.fn()}
      />
    </RelationLoaderProvider>,
  );
  return onChange;
}

const twoOptions: RelationLoader = async () => [
  { value: "1", label: "Acme" },
  { value: "2", label: "Globex" },
];

describe("RelationField", () => {
  it("single-select picks one option and closes", async () => {
    const onChange = renderRelation({}, twoOptions);
    fireEvent.click(screen.getByRole("button", { name: /Search/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Acme/ }));
    expect(onChange).toHaveBeenCalledWith("1");
  });

  it("multi-select toggles several and removes one", async () => {
    const onChange = vi.fn();
    render(
      <RelationLoaderProvider loader={twoOptions}>
        <RelationField
          field={fld({ field_type: "multi_lookup" })}
          id="field-rel"
          value={["1"]}
          onChange={onChange}
          onBlur={vi.fn()}
        />
      </RelationLoaderProvider>,
    );
    // existing selection shows a badge with the id (label not yet loaded)
    expect(screen.getByText("1")).toBeInTheDocument();
    // remove it
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows 'No matches' when the loader returns nothing", async () => {
    renderRelation({}, async () => []);
    fireEvent.click(screen.getByRole("button", { name: /Search/ }));
    expect(await screen.findByText("No matches")).toBeInTheDocument();
  });
});

describe("defaultRelationLoader", () => {
  beforeEach(() => vi.mocked(apiGet).mockReset());

  it("returns [] when no target entity is configured", async () => {
    const out = await defaultRelationLoader(fld({ config: {} }), "x");
    expect(out).toEqual([]);
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("maps records to {value,label} and includes a contains filter for a query", async () => {
    vi.mocked(apiGet).mockResolvedValue({ results: [{ id: "1", name: "Acme" }] });
    const out = await defaultRelationLoader(fld(), "ac");
    expect(out).toEqual([{ value: "1", label: "Acme" }]);
    const path = vi.mocked(apiGet).mock.calls[0][0] as string;
    expect(path).toContain("/api/v1/data/company/");
    expect(path).toContain("filter=");
  });

  it("omits the filter when there is no query", async () => {
    vi.mocked(apiGet).mockResolvedValue({ results: [] });
    await defaultRelationLoader(fld(), "");
    const path = vi.mocked(apiGet).mock.calls[0][0] as string;
    expect(path).not.toContain("filter=");
  });
});
