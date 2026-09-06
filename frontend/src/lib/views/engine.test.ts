import { describe, expect, it } from "vitest";

import type { EntityMeta, FieldMeta } from "@/lib/metadata/types";
import type { SavedView } from "@/lib/saved-views/api";

import {
  applySavedView,
  defaultViewConfig,
  hasField,
  validateViewDefinition,
  viewToNql,
} from "./engine";
import type { ViewDefinition } from "./types";

function field(slug: string, field_type: string): FieldMeta {
  return { slug, name: slug, field_type } as unknown as FieldMeta;
}

const entity = {
  id: "e1",
  slug: "deals",
  name: "Deal",
  plural_name: "Deals",
  title_field_slug: "name",
  fields: [
    field("name", "text"),
    field("stage", "select"),
    field("due", "date"),
    field("start", "date"),
    field("end", "date"),
    field("manager", "lookup"),
    field("amount", "currency"),
    field("lat", "decimal"),
    field("lng", "decimal"),
  ],
} as unknown as EntityMeta;

const def = (kind: ViewDefinition["kind"], config: Record<string, unknown>): ViewDefinition => ({
  kind,
  config,
});

describe("hasField", () => {
  it("checks field existence safely", () => {
    expect(hasField(entity, "stage")).toBe(true);
    expect(hasField(entity, "missing")).toBe(false);
    expect(hasField(entity, undefined)).toBe(false);
  });
});

describe("validateViewDefinition — valid configs", () => {
  it.each([
    ["kanban", { groupField: "stage" }],
    ["calendar", { dateField: "due" }],
    ["timeline", { dateField: "due" }],
    ["tree", { parentField: "manager" }],
    ["org_chart", { parentField: "manager" }],
    ["map", { latField: "lat", lngField: "lng" }],
    ["pivot", { rowField: "stage", colField: "stage", valueField: "amount", agg: "sum" }],
    ["chart", { chartType: "bar", groupField: "stage", valueField: "amount", agg: "sum" }],
    ["gantt", { startField: "start", endField: "end" }],
    ["dashboard", { widgets: [{ id: "w1", title: "T", kind: "metric", config: { agg: "count" } }] }],
  ] as const)("%s validates", (kind, config) => {
    expect(validateViewDefinition(def(kind, config), entity).valid).toBe(true);
  });

  it("allows count pivots/charts without a value field", () => {
    expect(validateViewDefinition(def("pivot", { rowField: "stage", colField: "stage", agg: "count" }), entity).valid).toBe(true);
  });
});

describe("validateViewDefinition — invalid configs", () => {
  it("flags a missing required field", () => {
    expect(validateViewDefinition(def("kanban", {}), entity).errors).toContain("Group field is required.");
  });
  it("flags a field that isn't on the entity", () => {
    const r = validateViewDefinition(def("calendar", { dateField: "ghost" }), entity);
    expect(r.valid).toBe(false);
    expect(r.errors[0]).toMatch(/not a field/);
  });
  it("requires a value field for non-count aggregations", () => {
    const r = validateViewDefinition(def("chart", { chartType: "bar", groupField: "stage", agg: "sum" }), entity);
    expect(r.errors).toContain("Value field is required.");
  });
  it("requires a chart type", () => {
    expect(
      validateViewDefinition(def("chart", { groupField: "stage", agg: "count" }), entity).errors,
    ).toContain("A chart type is required.");
  });
  it("requires at least one dashboard widget", () => {
    expect(validateViewDefinition(def("dashboard", { widgets: [] }), entity).errors).toContain(
      "Add at least one widget.",
    );
  });
  it("rejects an unknown kind", () => {
    expect(validateViewDefinition({ kind: "bogus" as ViewDefinition["kind"], config: {} }, entity).valid).toBe(false);
  });
});

describe("defaultViewConfig", () => {
  it("auto-picks sensible fields per kind", () => {
    expect(defaultViewConfig("kanban", entity)).toMatchObject({ groupField: "stage", titleField: "name" });
    expect(defaultViewConfig("calendar", entity)).toMatchObject({ dateField: "due" });
    expect(defaultViewConfig("chart", entity)).toMatchObject({ chartType: "bar", groupField: "stage", valueField: "amount", agg: "sum" });
    expect(defaultViewConfig("gantt", entity)).toMatchObject({ startField: "due", endField: "start" });
    expect(defaultViewConfig("dashboard", entity)).toEqual({ widgets: [] });
  });
  it("defaults the remaining kinds", () => {
    expect(defaultViewConfig("timeline", entity)).toMatchObject({ dateField: "due", dir: "desc" });
    expect(defaultViewConfig("tree", entity)).toMatchObject({ labelField: "name" });
    expect(defaultViewConfig("org_chart", entity)).toMatchObject({ labelField: "name" });
    expect(defaultViewConfig("map", entity)).toMatchObject({ labelField: "name" });
    expect(defaultViewConfig("pivot", entity)).toMatchObject({ agg: "sum", valueField: "amount" });
  });

  it("a freshly-defaulted kanban validates", () => {
    expect(validateViewDefinition(def("kanban", defaultViewConfig("kanban", entity)), entity).valid).toBe(true);
  });
});

describe("applySavedView (personalization)", () => {
  const sv = (over: Partial<SavedView> = {}): SavedView => ({
    id: "v1",
    entity_id: "e1",
    name: "Mine",
    hidden_field_slugs: [],
    column_widths: {},
    personal_filters: [],
    sort_overrides: [],
    group_by_override: "",
    is_pinned: false,
    ...over,
  });

  it("overrides the kanban group field", () => {
    const next = applySavedView(def("kanban", { groupField: "stage" }), sv({ group_by_override: "manager" }));
    expect(next.config.groupField).toBe("manager");
  });
  it("flips timeline direction from a sort override", () => {
    const next = applySavedView(def("timeline", { dateField: "due", dir: "asc" }), sv({ sort_overrides: [{ field: "due", direction: "desc" }] }));
    expect(next.config.dir).toBe("desc");
  });
  it("leaves config untouched when nothing applies", () => {
    expect(applySavedView(def("pivot", { rowField: "stage" }), sv()).config).toEqual({ rowField: "stage" });
  });
});

describe("viewToNql (NQL projection)", () => {
  it("selects only the fields the view references", () => {
    const q = viewToNql(def("map", { latField: "lat", lngField: "lng", labelField: "name" }), entity);
    expect(q.entity).toBe("deals");
    expect(new Set(q.select)).toEqual(new Set(["lat", "lng", "name"]));
  });
  it("adds a sort for timeline using its direction", () => {
    const q = viewToNql(def("timeline", { dateField: "due", dir: "desc" }), entity);
    expect(q.sort).toEqual([{ field: "due", direction: "desc" }]);
  });
  it("ignores config fields not on the entity", () => {
    const q = viewToNql(def("kanban", { groupField: "ghost", titleField: "name" }), entity);
    expect(q.select).toEqual(["name"]);
  });

  it("sorts a gantt by its date field ascending by default", () => {
    const q = viewToNql(def("gantt", { startField: "start", endField: "end", dateField: "due" }), entity);
    expect(q.sort).toEqual([{ field: "due", direction: "asc" }]);
  });
});
