/**
 * View-engine types (Phase F2.1). The engine and every view consume the SAME inputs —
 * `Row[]` (from the F1.7 records runtime / F1.9 NQL), entity metadata, and a `ViewDefinition`
 * (the saved-view config). No view has its own API; everything is metadata-driven and pure.
 */
import type { EntityMeta } from "@/lib/metadata/types";

export type Row = Record<string, unknown>;

export type ViewKind =
  | "kanban"
  | "calendar"
  | "tree"
  | "org_chart"
  | "timeline"
  | "map"
  | "chart"
  | "dashboard"
  | "pivot"
  | "gantt";

export type Agg = "count" | "sum" | "avg" | "min" | "max";
export type SortDir = "asc" | "desc";
export type ChartType = "bar" | "line" | "area" | "pie";

/** Per-kind configuration. A `ViewDefinition` is `{ kind, config }`. */
export interface KanbanConfig {
  groupField: string;
  titleField?: string;
}
export interface CalendarConfig {
  dateField: string;
  titleField?: string;
}
export interface HierarchyConfig {
  parentField: string;
  labelField?: string;
}
export interface TimelineConfig {
  dateField: string;
  titleField?: string;
  dir?: SortDir;
}
export interface MapConfig {
  latField: string;
  lngField: string;
  labelField?: string;
}
export interface PivotConfig {
  rowField: string;
  colField: string;
  valueField?: string | null;
  agg: Agg;
}
export interface ChartConfig {
  chartType: ChartType;
  groupField: string;
  valueField?: string | null;
  agg: Agg;
}
export interface GanttConfig {
  startField: string;
  endField: string;
  labelField?: string;
  progressField?: string | null;
  dependencyField?: string | null;
}
export interface DashboardConfig {
  widgets: DashboardWidgetDef[];
}
export interface DashboardWidgetDef {
  id: string;
  title: string;
  kind: "chart" | "pivot" | "metric";
  config: ChartConfig | PivotConfig | MetricConfig;
}
export interface MetricConfig {
  valueField?: string | null;
  agg: Agg;
}

export type ViewConfig =
  | ({ kind: "kanban" } & KanbanConfig)
  | ({ kind: "calendar" } & CalendarConfig)
  | ({ kind: "tree" } & HierarchyConfig)
  | ({ kind: "org_chart" } & HierarchyConfig)
  | ({ kind: "timeline" } & TimelineConfig)
  | ({ kind: "map" } & MapConfig)
  | ({ kind: "chart" } & ChartConfig)
  | ({ kind: "dashboard" } & DashboardConfig)
  | ({ kind: "pivot" } & PivotConfig)
  | ({ kind: "gantt" } & GanttConfig);

export interface ViewDefinition {
  kind: ViewKind;
  config: Record<string, unknown>;
}

/** Result of validating a ViewDefinition against entity metadata. */
export interface ViewValidation {
  valid: boolean;
  errors: string[];
}

// ── shared derived shapes ────────────────────────────────────────────────────────────
export interface Group {
  key: string;
  label: string;
  records: Row[];
}

export interface TreeNode {
  row: Row;
  children: TreeNode[];
  depth: number;
}

export interface PivotResult {
  rowKeys: string[];
  colKeys: string[];
  cells: Record<string, number>; // keyed by cellKey(rowKey, colKey)
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  grandTotal: number;
}

export interface CalendarEvent {
  id: string;
  day: string; // yyyy-mm-dd
  title: string;
  row: Row;
}

export interface GanttItem {
  id: string;
  row: Row;
  start: number; // ms epoch
  end: number;
  left: number; // % across the span
  width: number; // %
  progress: number; // 0..1
  dependsOn: string[];
}

export interface GeoMarker {
  id: string;
  row: Row;
  lat: number;
  lng: number;
  x: number; // 0..100 projected
  y: number; // 0..100 projected (north up)
  label: string;
}

export interface ChartDataset {
  labels: string[];
  values: number[];
  agg: Agg;
}

/** Common helpers shared by every module. */
export function rowId(row: Row): string {
  return String(row.id ?? "");
}

export function toText(v: unknown): string {
  if (v === null || v === undefined || v === "") return "";
  if (Array.isArray(v)) return v.map(toText).join(", ");
  return String(v);
}

export function fieldsOfType(entity: EntityMeta, types: string[]): EntityMeta["fields"] {
  return (entity.fields ?? []).filter((f) => types.includes(f.field_type));
}

export const GROUPABLE_TYPES = ["select", "status", "boolean", "user"];
export const DATE_TYPES = ["date", "datetime"];
export const NUMERIC_TYPES = ["integer", "decimal", "currency", "percent", "rating", "duration"];
