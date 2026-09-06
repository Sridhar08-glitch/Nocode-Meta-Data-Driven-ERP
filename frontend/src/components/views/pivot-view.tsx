"use client";

import { cellKey, pivot } from "@/lib/views/pivot";
import { type Agg, type Row } from "@/lib/views/types";

export interface PivotViewProps {
  rows: Row[];
  rowField: string;
  colField: string;
  valueField?: string | null;
  agg: Agg;
  /** Drill-down: open the rows behind a cell (rowKey/colKey null = whole row/col total). */
  onDrill?: (rowKey: string | null, colKey: string | null) => void;
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

/** Pivot table with row/column aggregation and drill-down (Phase F2.1). */
export function PivotView({ rows, rowField, colField, valueField, agg, onDrill }: PivotViewProps) {
  const p = pivot(rows, rowField, colField, valueField ?? null, agg);

  const Cell = ({ value, onClick }: { value: number; onClick?: () => void }) =>
    onClick ? (
      <button className="w-full px-3 py-1 text-right tabular-nums hover:bg-muted" onClick={onClick}>
        {fmt(value)}
      </button>
    ) : (
      <span className="block px-3 py-1 text-right tabular-nums">{fmt(value)}</span>
    );

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-1 text-left font-medium">{agg}</th>
            {p.colKeys.map((ck) => (
              <th key={ck} className="px-3 py-1 text-right font-medium">
                {ck}
              </th>
            ))}
            <th className="px-3 py-1 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {p.rowKeys.map((rk) => (
            <tr key={rk} className="border-b">
              <th className="px-3 py-1 text-left font-medium">{rk}</th>
              {p.colKeys.map((ck) => (
                <td key={ck} className="p-0">
                  <Cell value={p.cells[cellKey(rk, ck)] ?? 0} onClick={onDrill ? () => onDrill(rk, ck) : undefined} />
                </td>
              ))}
              <td className="p-0">
                <Cell value={p.rowTotals[rk] ?? 0} onClick={onDrill ? () => onDrill(rk, null) : undefined} />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t bg-muted/30 font-medium">
            <th className="px-3 py-1 text-left">Total</th>
            {p.colKeys.map((ck) => (
              <td key={ck} className="p-0">
                <Cell value={p.colTotals[ck] ?? 0} onClick={onDrill ? () => onDrill(null, ck) : undefined} />
              </td>
            ))}
            <td className="px-3 py-1 text-right tabular-nums">{fmt(p.grandTotal)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
