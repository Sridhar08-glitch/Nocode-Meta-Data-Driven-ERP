/**
 * Reporting client (Phase F2.3) — reports + dashboards over `/api/v1/reports/` and
 * `/api/v1/dashboards/`. Run/pivot/snapshot/export/validate for reports; nested widget CRUD +
 * run + PDF for dashboards. Exports are binary downloads. No client-side analytics — the backend
 * compiles NQL; the dashboard run returns per-widget results (the chart engine renders them).
 */
import { apiGet, apiSend, downloadFile } from "@/lib/api/request";

export type ReportType = "table" | "chart" | "pivot" | "funnel" | "cohort" | "kanban_summary" | "timeline";

export interface Report {
  id: string;
  name: string;
  slug: string;
  description: string;
  report_type: ReportType;
  nql_ast: Record<string, unknown>;
  nql_source: string;
  display_config: Record<string, unknown>;
  source_entity_ids: string[];
  schedule_cron: string;
  schedule_recipients: string[];
  last_run_at: string | null;
  is_public: boolean;
  shared_with: unknown[];
  created_at: string;
  updated_at: string;
}
export interface ReportWrite {
  name: string;
  slug: string;
  description?: string;
  report_type?: ReportType;
  nql_ast: Record<string, unknown>;
  nql_source?: string;
  display_config?: Record<string, unknown>;
  schedule_cron?: string;
  schedule_recipients?: string[];
  is_public?: boolean;
}

export interface TableRunResult {
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
  total_count: number;
  truncated: boolean;
}
export interface PivotRunResult {
  row_field: string;
  column_field: string | null;
  agg: string;
  row_values: string[];
  column_values: string[];
  matrix: (number | null)[][];
}
export type RunResult = TableRunResult | PivotRunResult;

export function isPivotResult(r: RunResult): r is PivotRunResult {
  return (r as PivotRunResult).matrix !== undefined;
}

export interface ReportSnapshot {
  id: string;
  report_id: string;
  row_count: number;
  data: Record<string, unknown>[];
  generated_by: string | null;
  duration_ms: number;
  created_at: string;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export type DashboardWidgetType = "report" | "metric_card" | "iframe" | "text" | "activity_feed" | "quick_links";

export interface DashboardWidget {
  id: string;
  dashboard_id: string;
  widget_type: DashboardWidgetType;
  title: string;
  report_id: string | null;
  grid_x: number;
  grid_y: number;
  grid_w: number;
  grid_h: number;
  config: Record<string, unknown>;
  refresh_interval_seconds: number;
  source_report_ids: string[];
  created_at: string;
  updated_at: string;
}
export type DashboardWidgetWrite = Partial<Omit<DashboardWidget, "id" | "dashboard_id" | "created_at" | "updated_at">> & {
  widget_type: DashboardWidgetType;
};

export interface Dashboard {
  id: string;
  name: string;
  slug: string;
  description: string;
  layout: unknown[];
  is_public: boolean;
  is_default: boolean;
  shared_with: unknown[];
  widgets: DashboardWidget[];
  created_at: string;
  updated_at: string;
}
export interface DashboardWrite {
  name: string;
  slug: string;
  description?: string;
  layout?: unknown[];
  is_public?: boolean;
  is_default?: boolean;
}

/** A widget result from the dashboard run: base + exactly one of result / error / config. */
export interface WidgetResult {
  widget_id: string;
  widget_type: DashboardWidgetType;
  title: string;
  result?: RunResult;
  error?: string;
  config?: Record<string, unknown>;
}
export interface DashboardRunResult {
  dashboard_id: string;
  name: string;
  widgets: WidgetResult[];
}

export const REPORT_TYPE_OPTIONS: { value: ReportType; label: string }[] = [
  { value: "table", label: "Table" },
  { value: "chart", label: "Chart" },
  { value: "pivot", label: "Pivot" },
  { value: "funnel", label: "Funnel" },
  { value: "timeline", label: "Timeline" },
  { value: "kanban_summary", label: "Kanban summary" },
  { value: "cohort", label: "Cohort" },
];

export const WIDGET_TYPE_OPTIONS: { value: DashboardWidgetType; label: string }[] = [
  { value: "report", label: "Report" },
  { value: "metric_card", label: "Metric card" },
  { value: "text", label: "Text" },
  { value: "iframe", label: "Embed (iframe)" },
  { value: "quick_links", label: "Quick links" },
  { value: "activity_feed", label: "Activity feed" },
];

const R = "/api/v1/reports";
const D = "/api/v1/dashboards";

export const reportsApi = {
  list: (reportType?: string) =>
    apiGet<Paged<Report>>(`${R}/${reportType ? `?report_type=${encodeURIComponent(reportType)}` : ""}`),
  get: (id: string) => apiGet<Report>(`${R}/${id}/`),
  create: (data: ReportWrite) => apiSend<Report>(`${R}/`, "POST", data),
  update: (id: string, data: Partial<ReportWrite>) => apiSend<Report>(`${R}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${R}/${id}/`, "DELETE"),
  run: (id: string) => apiSend<RunResult>(`${R}/${id}/run/`, "POST"),
  snapshot: (id: string) => apiSend<ReportSnapshot>(`${R}/${id}/snapshot/`, "POST"),
  snapshots: (id: string) => apiGet<Paged<ReportSnapshot>>(`${R}/${id}/snapshots/`),
  validateNql: (body: { nql_source?: string; nql_ast?: Record<string, unknown> }) =>
    apiSend<{ valid: boolean; errors: string[] }>(`${R}/validate-nql/`, "POST", body),
  exportCsv: (id: string, slug: string) => downloadFile(`${R}/${id}/export/csv/`, `${slug}.csv`),
  exportXlsx: (id: string, slug: string) => downloadFile(`${R}/${id}/export/xlsx/`, `${slug}.xlsx`),
  exportPdf: (id: string, slug: string) => downloadFile(`${R}/${id}/export/pdf/`, `${slug}.pdf`),
};

export const dashboardsApi = {
  list: () => apiGet<Paged<Dashboard>>(`${D}/`),
  get: (id: string) => apiGet<Dashboard>(`${D}/${id}/`),
  create: (data: DashboardWrite) => apiSend<Dashboard>(`${D}/`, "POST", data),
  update: (id: string, data: Partial<DashboardWrite>) => apiSend<Dashboard>(`${D}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${D}/${id}/`, "DELETE"),
  run: (id: string) => apiSend<DashboardRunResult>(`${D}/${id}/run/`, "POST"),
  exportPdf: (id: string, slug: string) => downloadFile(`${D}/${id}/export/pdf/`, `${slug}.pdf`),
  widgets: (id: string) => apiGet<DashboardWidget[]>(`${D}/${id}/widgets/`),
  createWidget: (id: string, data: DashboardWidgetWrite) =>
    apiSend<DashboardWidget>(`${D}/${id}/widgets/`, "POST", data),
  updateWidget: (id: string, wid: string, data: Partial<DashboardWidgetWrite>) =>
    apiSend<DashboardWidget>(`${D}/${id}/widgets/${wid}/`, "PATCH", data),
  deleteWidget: (id: string, wid: string) => apiSend<null>(`${D}/${id}/widgets/${wid}/`, "DELETE"),
};
