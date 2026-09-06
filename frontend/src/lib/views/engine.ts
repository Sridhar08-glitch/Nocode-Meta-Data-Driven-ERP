/**
 * View engine (Phase F2.1) — the foundation every view shares: field discovery, view-definition
 * VALIDATION against entity metadata, sensible default configs, saved-view integration, and an
 * NQL projection. No React; pure functions only. Views never define their own API — they take
 * `Row[]` (from the F1.7 records runtime / F1.9 NQL) + metadata + a validated `ViewDefinition`.
 */
import type { EntityMeta } from "@/lib/metadata/types";
import { emptyQuery } from "@/lib/nql/builder";
import type { NqlQuery } from "@/lib/nql/types";
import type { SavedView } from "@/lib/saved-views/api";

import {
  type Agg,
  DATE_TYPES,
  fieldsOfType,
  GROUPABLE_TYPES,
  NUMERIC_TYPES,
  type ViewDefinition,
  type ViewKind,
  type ViewValidation,
} from "./types";

const AGGS: Agg[] = ["count", "sum", "avg", "min", "max"];

export function hasField(entity: EntityMeta, slug: unknown): boolean {
  return typeof slug === "string" && !!slug && (entity.fields ?? []).some((f) => f.slug === slug);
}

function str(config: Record<string, unknown>, key: string): string | undefined {
  const v = config[key];
  return typeof v === "string" && v ? v : undefined;
}

/** Validate a ViewDefinition's required field mappings against the entity. */
export function validateViewDefinition(def: ViewDefinition, entity: EntityMeta): ViewValidation {
  const errors: string[] = [];
  const c = def.config ?? {};
  const need = (key: string, label = key) => {
    const slug = str(c, key);
    if (!slug) errors.push(`${label} is required.`);
    else if (!hasField(entity, slug)) errors.push(`${label} "${slug}" is not a field on this entity.`);
  };
  const needAggValue = () => {
    const agg = c.agg;
    if (!AGGS.includes(agg as Agg)) errors.push("A valid aggregation is required.");
    if (agg && agg !== "count") need("valueField", "Value field");
  };

  switch (def.kind) {
    case "kanban":
      need("groupField", "Group field");
      break;
    case "calendar":
      need("dateField", "Date field");
      break;
    case "timeline":
      need("dateField", "Date field");
      break;
    case "tree":
    case "org_chart":
      need("parentField", def.kind === "org_chart" ? "Manager field" : "Parent field");
      break;
    case "map":
      need("latField", "Latitude field");
      need("lngField", "Longitude field");
      break;
    case "pivot":
      need("rowField", "Row field");
      need("colField", "Column field");
      needAggValue();
      break;
    case "chart":
      need("groupField", "Group field");
      if (!["bar", "line", "area", "pie"].includes(c.chartType as string))
        errors.push("A chart type is required.");
      needAggValue();
      break;
    case "gantt":
      need("startField", "Start date field");
      need("endField", "End date field");
      break;
    case "dashboard": {
      const widgets = c.widgets;
      if (!Array.isArray(widgets) || widgets.length === 0) errors.push("Add at least one widget.");
      break;
    }
    default:
      errors.push(`Unknown view kind "${(def as ViewDefinition).kind}".`);
  }
  return { valid: errors.length === 0, errors };
}

/** Auto-pick sensible field mappings for a kind so a new view is immediately usable. */
export function defaultViewConfig(kind: ViewKind, entity: EntityMeta): Record<string, unknown> {
  const group = fieldsOfType(entity, GROUPABLE_TYPES)[0]?.slug;
  const dates = fieldsOfType(entity, DATE_TYPES).map((f) => f.slug);
  const num = fieldsOfType(entity, NUMERIC_TYPES)[0]?.slug ?? null;
  const title = entity.title_field_slug || (entity.fields ?? [])[0]?.slug;

  switch (kind) {
    case "kanban":
      return { groupField: group, titleField: title };
    case "calendar":
      return { dateField: dates[0], titleField: title };
    case "timeline":
      return { dateField: dates[0], titleField: title, dir: "desc" };
    case "tree":
    case "org_chart":
      return { parentField: undefined, labelField: title };
    case "map":
      return { latField: undefined, lngField: undefined, labelField: title };
    case "pivot":
      return { rowField: group, colField: group, valueField: num, agg: num ? "sum" : "count" };
    case "chart":
      return { chartType: "bar", groupField: group, valueField: num, agg: num ? "sum" : "count" };
    case "gantt":
      return { startField: dates[0], endField: dates[1] ?? dates[0], progressField: null, dependencyField: null };
    case "dashboard":
      return { widgets: [] };
    default:
      return {};
  }
}

/** Saved-view integration: overlay a member's SavedView personalization onto a ViewDefinition. */
export function applySavedView(def: ViewDefinition, view: SavedView): ViewDefinition {
  const config = { ...def.config };
  // group_by_override personalizes the kanban/chart grouping
  if (view.group_by_override && (def.kind === "kanban" || def.kind === "chart")) {
    config.groupField = view.group_by_override;
  }
  // a sort override flips timeline direction
  if (def.kind === "timeline" && view.sort_overrides[0]) {
    config.dir = view.sort_overrides[0].direction;
  }
  return { kind: def.kind, config };
}

/** NQL integration: project a ViewDefinition to an NQL query (select needed fields + sort). */
export function viewToNql(def: ViewDefinition, entity: EntityMeta): NqlQuery {
  const q = emptyQuery(entity.slug);
  const c = def.config ?? {};
  const fields = new Set<string>();
  for (const key of [
    "groupField",
    "titleField",
    "dateField",
    "parentField",
    "labelField",
    "latField",
    "lngField",
    "rowField",
    "colField",
    "valueField",
    "startField",
    "endField",
    "progressField",
    "dependencyField",
  ]) {
    const slug = str(c, key);
    if (slug && hasField(entity, slug)) fields.add(slug);
  }
  q.select = Array.from(fields);
  if ((def.kind === "timeline" || def.kind === "gantt") && typeof c.dateField === "string") {
    q.sort = [{ field: c.dateField, direction: (c.dir as "asc" | "desc") ?? "asc" }];
  }
  return q;
}
