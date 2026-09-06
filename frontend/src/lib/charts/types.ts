/**
 * Chart engine types (Phase F2.2). A `ChartSpec` is a rendering layer over the F2.1 aggregation
 * model — it reuses `aggregateBy`/`pivot`/`groupByField` (no parallel analytics). Every produced
 * datum retains the source record ids so any chart element can drill down to its records.
 */
import type { Agg } from "@/lib/views/types";

export type ChartType =
  | "bar"
  | "horizontal_bar"
  | "stacked_bar"
  | "grouped_bar"
  | "line"
  | "multi_line"
  | "area"
  | "stacked_area"
  | "pie"
  | "donut"
  | "radar"
  | "radial_bar"
  | "scatter"
  | "bubble"
  | "composed"
  | "treemap"
  | "funnel"
  | "heatmap"
  | "waterfall"
  | "gauge";

/** How a chart type's dataset is built from records. */
export type ChartDataKind = "single" | "multi" | "xy" | "matrix";

/** The Recharts component family used to render. */
export type ChartRenderFamily =
  | "bar"
  | "line"
  | "area"
  | "pie"
  | "scatter"
  | "radar"
  | "radialBar"
  | "treemap"
  | "funnel"
  | "composed"
  | "heatmap"
  | "gauge"
  | "waterfall";

export interface AxisSpec {
  field: string;
  label?: string;
}

export interface SeriesSpec {
  /** Field whose distinct values split the data into series (multi-series charts). */
  field: string;
  label?: string;
}

export interface DrilldownSpec {
  enabled: boolean;
  /** Entity the underlying records belong to (records runtime resolves them). */
  entitySlug?: string;
}

export interface ChartSpec {
  type: ChartType;
  /** Category / x axis (group field for categorical, numeric x for xy). */
  x: AxisSpec;
  /** Series-splitting field for multi-series + matrix charts. */
  series?: SeriesSpec;
  /** Numeric y field for xy charts. */
  y?: AxisSpec;
  /** Bubble size field (xy only). */
  sizeField?: string | null;
  /** Aggregation for categorical/matrix charts. */
  agg: Agg;
  /** Value field aggregated (null/omitted → count). */
  valueField?: string | null;
  drilldown?: DrilldownSpec;
  options?: Record<string, unknown>;
}

// ── normalized chart data (what the renderer consumes; every datum keeps recordIds) ──
export interface ChartPoint {
  label: string;
  value: number;
  recordIds: string[];
}
export interface ChartSeriesData {
  name: string;
  points: ChartPoint[];
}
export interface XYPoint {
  x: number;
  y: number;
  size?: number;
  recordId: string;
  label: string;
}
export interface MatrixCell {
  row: string;
  col: string;
  value: number;
  recordIds: string[];
}

export type ChartData =
  | { kind: "categorical"; labels: string[]; series: ChartSeriesData[] }
  | { kind: "xy"; points: XYPoint[] }
  | { kind: "matrix"; rowKeys: string[]; colKeys: string[]; cells: MatrixCell[] };

/** A click target identifying which datum was selected (for drill-down). */
export type ChartSelector =
  | { kind: "label"; label: string }
  | { kind: "cell"; row: string; col: string }
  | { kind: "record"; recordId: string };

export interface ChartValidation {
  valid: boolean;
  errors: string[];
}
