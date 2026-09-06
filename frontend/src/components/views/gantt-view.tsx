"use client";

import { ganttItems } from "@/lib/views/gantt";
import { type GanttConfig, type Row, rowId, toText } from "@/lib/views/types";

export interface GanttViewProps {
  rows: Row[];
  config: GanttConfig;
}

/** Gantt chart: start/end bars with progress overlay (Phase F2.1). */
export function GanttView({ rows, config }: GanttViewProps) {
  const items = ganttItems(rows, config);
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">No records with valid start/end dates.</p>;
  }
  const label = (row: Row) => toText(config.labelField ? row[config.labelField] : row.id) || rowId(row);

  return (
    <ul aria-label="Gantt" className="space-y-1">
      {items.map((item) => (
        <li key={item.id} className="grid grid-cols-[10rem_1fr] items-center gap-2 text-sm">
          <span className="truncate">{label(item.row)}</span>
          <div className="relative h-5 rounded bg-muted/40">
            <div
              aria-label={`${label(item.row)} bar`}
              data-progress={item.progress}
              className="absolute top-0 h-5 rounded bg-primary/30"
              style={{ left: `${item.left}%`, width: `${item.width}%` }}
            >
              <div
                className="h-full rounded bg-primary"
                style={{ width: `${item.progress * 100}%` }}
              />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
