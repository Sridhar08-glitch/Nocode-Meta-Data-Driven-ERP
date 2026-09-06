"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Funnel,
  FunnelChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { type Row } from "@/lib/views/types";

import { resolveDrilldown } from "./drilldown";
import { getChartType } from "./registry";
import { buildChartData } from "./spec";
import type { ChartData, ChartSelector, ChartSpec } from "./types";

const PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2", "#db2777"];

/** Recharts v3 per-component `data` types are stricter than our normalized arrays; cast at the prop. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const chartData = (xs: unknown[]): any[] => xs as any[];

export interface ChartRendererProps {
  spec: ChartSpec;
  rows: Row[];
  loading?: boolean;
  error?: boolean;
  /** Fires when a chart element is clicked, with the resolved source records. */
  onDrill?: (selector: ChartSelector, records: Row[]) => void;
  height?: number;
}

function isEmpty(data: ChartData): boolean {
  if (data.kind === "xy") return data.points.length === 0;
  if (data.kind === "matrix") return data.cells.length === 0;
  return data.series.length === 0 || data.series.every((s) => s.points.length === 0);
}

/** Renders any of the 20 chart types from a ChartSpec, with an accessible data table + drill-down. */
export function ChartRenderer({ spec, rows, loading, error, onDrill, height = 280 }: ChartRendererProps) {
  const def = getChartType(spec.type);
  if (!def) return <ErrorState title="Unsupported chart type" />;
  if (loading) return <Skeleton style={{ height }} className="w-full" />;
  if (error) return <ErrorState title="Couldn't load chart data" />;

  const data = buildChartData(spec, rows);
  if (isEmpty(data)) return <EmptyState title="No data to chart" />;

  const drill = (selector: ChartSelector) => onDrill?.(selector, resolveDrilldown(spec, rows, selector));

  return (
    <figure className="space-y-2" aria-label={`${def.label} chart`}>
      <div style={{ height }} data-chart-family={def.render}>
        <ResponsiveContainer width="100%" height="100%">
          <ChartCanvas data={data} def={def} />
        </ResponsiveContainer>
      </div>
      <DataTable data={data} onDrill={onDrill ? drill : undefined} caption={`${def.label} data`} />
    </figure>
  );
}

/** The Recharts canvas for a render family (best-effort visual; the table is the a11y source). */
function ChartCanvas({ data, def }: { data: ChartData; def: NonNullable<ReturnType<typeof getChartType>> }) {
  if (data.kind === "xy") {
    return (
      <ScatterChart>
        <CartesianGrid />
        <XAxis type="number" dataKey="x" />
        <YAxis type="number" dataKey="y" />
        {def.options?.bubble && <ZAxis type="number" dataKey="size" range={[40, 400]} />}
        <Tooltip />
        <Scatter data={chartData(data.points)} fill={PALETTE[0]} />
      </ScatterChart>
    );
  }
  if (data.kind === "matrix") {
    // heatmap rendered as a DOM grid (Recharts has no native heatmap)
    const max = Math.max(...data.cells.map((c) => c.value), 1);
    return (
      <div className="grid h-full gap-px" style={{ gridTemplateColumns: `repeat(${data.colKeys.length}, 1fr)` }}>
        {data.cells.map((c) => (
          <div
            key={`${c.row}/${c.col}`}
            title={`${c.row} × ${c.col}: ${c.value}`}
            style={{ backgroundColor: `rgba(37,99,235,${c.value / max})` }}
          />
        ))}
      </div>
    );
  }

  // categorical → rows keyed by label, one numeric key per series
  const chartRows = data.labels.map((label, i) => {
    const r: Record<string, unknown> = { label };
    for (const s of data.series) r[s.name] = s.points[i]?.value ?? 0;
    return r;
  });
  const keys = data.series.map((s) => s.name);

  switch (def.render) {
    case "line":
    case "composed":
      return (
        <LineChart data={chartData(chartRows)}>
          <CartesianGrid /> <XAxis dataKey="label" /> <YAxis /> <Tooltip /> <Legend />
          {keys.map((k, i) => (
            <Line key={k} dataKey={k} stroke={PALETTE[i % PALETTE.length]} />
          ))}
        </LineChart>
      );
    case "area":
      return (
        <AreaChart data={chartData(chartRows)}>
          <CartesianGrid /> <XAxis dataKey="label" /> <YAxis /> <Tooltip /> <Legend />
          {keys.map((k, i) => (
            <Area key={k} dataKey={k} stackId={def.options?.stacked ? "1" : undefined} fill={PALETTE[i % PALETTE.length]} stroke={PALETTE[i % PALETTE.length]} />
          ))}
        </AreaChart>
      );
    case "pie": {
      const slices = data.series[0]?.points ?? [];
      return (
        <PieChart>
          <Tooltip />
          <Pie data={chartData(slices)} dataKey="value" nameKey="label" innerRadius={def.options?.donut ? "50%" : 0}>
            {slices.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
        </PieChart>
      );
    }
    case "radar":
      return (
        <RadarChart data={chartData(chartRows)}>
          <PolarGrid /> <PolarAngleAxis dataKey="label" /> <Tooltip /> <Legend />
          {keys.map((k, i) => (
            <Radar key={k} dataKey={k} stroke={PALETTE[i % PALETTE.length]} fill={PALETTE[i % PALETTE.length]} fillOpacity={0.4} />
          ))}
        </RadarChart>
      );
    case "radialBar":
      return (
        <RadialBarChart data={chartData(data.series[0]?.points ?? [])} innerRadius="20%" outerRadius="100%">
          <RadialBar dataKey="value" />
          <Tooltip />
        </RadialBarChart>
      );
    case "treemap":
      return <Treemap data={chartData(data.series[0]?.points ?? [])} dataKey="value" nameKey="label" />;
    case "funnel":
      return (
        <FunnelChart>
          <Tooltip />
          <Funnel data={chartData(data.series[0]?.points ?? [])} dataKey="value" nameKey="label" />
        </FunnelChart>
      );
    case "gauge": {
      const p = data.series[0]?.points[0];
      const total = (data.series[0]?.points ?? []).reduce((a, b) => a + b.value, 0) || 1;
      return (
        <ComposedChart data={chartData([{ label: p?.label, value: p?.value, rest: total - (p?.value ?? 0) }])}>
          <Bar dataKey="value" stackId="g" fill={PALETTE[1]} />
          <Bar dataKey="rest" stackId="g" fill="#e5e7eb" />
        </ComposedChart>
      );
    }
    case "waterfall": {
      let cum = 0;
      const wf = (data.series[0]?.points ?? []).map((pt) => {
        const base = cum;
        cum += pt.value;
        return { label: pt.label, base, value: pt.value };
      });
      return (
        <BarChart data={chartData(wf)}>
          <CartesianGrid /> <XAxis dataKey="label" /> <YAxis /> <Tooltip />
          <Bar dataKey="base" stackId="w" fillOpacity={0} />
          <Bar dataKey="value" stackId="w" fill={PALETTE[0]} />
        </BarChart>
      );
    }
    default: // bar (+ stacked / grouped / horizontal)
      return (
        <BarChart data={chartData(chartRows)} layout={def.options?.horizontal ? "vertical" : "horizontal"}>
          <CartesianGrid />
          {def.options?.horizontal ? <XAxis type="number" /> : <XAxis dataKey="label" />}
          {def.options?.horizontal ? <YAxis type="category" dataKey="label" /> : <YAxis />}
          <Tooltip /> <Legend />
          {keys.map((k, i) => (
            <Bar key={k} dataKey={k} stackId={def.options?.stacked ? "1" : undefined} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </BarChart>
      );
  }
}

/** Accessible, always-rendered data table — the a11y fallback and the drill-down click surface. */
function DataTable({
  data,
  caption,
  onDrill,
}: {
  data: ChartData;
  caption: string;
  onDrill?: (selector: ChartSelector) => void;
}) {
  if (data.kind === "xy") {
    return (
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th className="text-left">Point</th>
            <th className="text-right">X</th>
            <th className="text-right">Y</th>
          </tr>
        </thead>
        <tbody>
          {data.points.map((p) => (
            <tr key={p.recordId}>
              <td>
                <DrillCell label={p.label || p.recordId} onClick={onDrill && (() => onDrill({ kind: "record", recordId: p.recordId }))} />
              </td>
              <td className="text-right tabular-nums">{p.x}</td>
              <td className="text-right tabular-nums">{p.y}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (data.kind === "matrix") {
    return (
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <tbody>
          {data.cells.map((c) => (
            <tr key={`${c.row}/${c.col}`}>
              <td>
                <DrillCell label={`${c.row} × ${c.col}`} onClick={onDrill && (() => onDrill({ kind: "cell", row: c.row, col: c.col }))} />
              </td>
              <td className="text-right tabular-nums">{c.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  const multi = data.series.length > 1;
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th className="text-left">Category</th>
          {data.series.map((s) => (
            <th key={s.name} className="text-right">
              {s.name}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.labels.map((label, i) => (
          <tr key={label}>
            <td>
              {multi ? (
                label
              ) : (
                <DrillCell label={label} onClick={onDrill && (() => onDrill({ kind: "label", label }))} />
              )}
            </td>
            {data.series.map((s) => {
              const pt = s.points[i];
              return (
                <td key={s.name} className="text-right tabular-nums">
                  {multi && onDrill ? (
                    <DrillCell
                      label={String(pt?.value ?? 0)}
                      onClick={() => onDrill({ kind: "cell", row: label, col: s.name })}
                    />
                  ) : (
                    (pt?.value ?? 0)
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DrillCell({ label, onClick }: { label: string; onClick?: () => void }) {
  if (!onClick) return <span>{label}</span>;
  return (
    <button className="hover:underline" onClick={onClick}>
      {label}
    </button>
  );
}
