/**
 * Chart registry (Phase F2.2) — the single, extensible mapping from chart type → metadata
 * (how its data is built + which Recharts family renders it). Adding a chart type = one entry.
 */
import type { ChartDataKind, ChartRenderFamily, ChartType } from "./types";

export interface ChartTypeDef {
  type: ChartType;
  label: string;
  dataKind: ChartDataKind;
  render: ChartRenderFamily;
  /** Render options (stacked bars, horizontal, donut hole, bubble size, smooth lines). */
  options?: {
    stacked?: boolean;
    grouped?: boolean;
    horizontal?: boolean;
    donut?: boolean;
    bubble?: boolean;
    smooth?: boolean;
  };
}

const DEFS: ChartTypeDef[] = [
  { type: "bar", label: "Bar", dataKind: "single", render: "bar" },
  { type: "horizontal_bar", label: "Horizontal bar", dataKind: "single", render: "bar", options: { horizontal: true } },
  { type: "stacked_bar", label: "Stacked bar", dataKind: "multi", render: "bar", options: { stacked: true } },
  { type: "grouped_bar", label: "Grouped bar", dataKind: "multi", render: "bar", options: { grouped: true } },
  { type: "line", label: "Line", dataKind: "single", render: "line" },
  { type: "multi_line", label: "Multi-line", dataKind: "multi", render: "line" },
  { type: "area", label: "Area", dataKind: "single", render: "area" },
  { type: "stacked_area", label: "Stacked area", dataKind: "multi", render: "area", options: { stacked: true } },
  { type: "pie", label: "Pie", dataKind: "single", render: "pie" },
  { type: "donut", label: "Donut", dataKind: "single", render: "pie", options: { donut: true } },
  { type: "radar", label: "Radar", dataKind: "multi", render: "radar" },
  { type: "radial_bar", label: "Radial bar", dataKind: "single", render: "radialBar" },
  { type: "scatter", label: "Scatter", dataKind: "xy", render: "scatter" },
  { type: "bubble", label: "Bubble", dataKind: "xy", render: "scatter", options: { bubble: true } },
  { type: "composed", label: "Composed", dataKind: "multi", render: "composed" },
  { type: "treemap", label: "Treemap", dataKind: "single", render: "treemap" },
  { type: "funnel", label: "Funnel", dataKind: "single", render: "funnel" },
  { type: "heatmap", label: "Heatmap", dataKind: "matrix", render: "heatmap" },
  { type: "waterfall", label: "Waterfall", dataKind: "single", render: "waterfall" },
  { type: "gauge", label: "Gauge", dataKind: "single", render: "gauge" },
];

const BY_TYPE = new Map<ChartType, ChartTypeDef>(DEFS.map((d) => [d.type, d]));

export const CHART_TYPES: readonly ChartTypeDef[] = DEFS;

export function getChartType(type: ChartType): ChartTypeDef | undefined {
  return BY_TYPE.get(type);
}

export function isMultiSeries(type: ChartType): boolean {
  return getChartType(type)?.dataKind === "multi";
}
