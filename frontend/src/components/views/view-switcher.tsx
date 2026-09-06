"use client";

import { ChartRenderer } from "@/lib/charts/renderer";
import type { ChartType as ChartTypeName } from "@/lib/charts/types";
import type { EntityMeta } from "@/lib/metadata/types";
import { validateViewDefinition } from "@/lib/views/engine";
import {
  type Agg,
  type DashboardWidgetDef,
  type Row,
  type SortDir,
  type ViewDefinition,
} from "@/lib/views/types";

import { CalendarView } from "./calendar-view";
import { DashboardView } from "./dashboard-view";
import { GanttView } from "./gantt-view";
import { HierarchyView } from "./hierarchy-view";
import { KanbanView } from "./kanban-view";
import { MapView } from "./map-view";
import { PivotView } from "./pivot-view";
import { TimelineView } from "./timeline-view";

export interface ViewSwitcherProps {
  definition: ViewDefinition;
  rows: Row[];
  entity: EntityMeta;
  /** Persist a record field patch (optimistic views call this); rejecting triggers rollback. */
  onUpdate?: (id: string, patch: Record<string, unknown>) => Promise<unknown>;
  /** Chart drill-down: resolved source records for a clicked chart element. */
  onDrillRecords?: (records: Row[]) => void;
}

const s = (c: Record<string, unknown>, k: string) => (typeof c[k] === "string" ? (c[k] as string) : undefined);

/**
 * The single entry point for every view (Phase F2.1): validates the ViewDefinition against the
 * entity, then renders the matching component fed by the SAME `rows` + metadata. No view-specific
 * data API — interactive views persist via the shared `onUpdate`.
 */
export function ViewSwitcher({ definition, rows, entity, onUpdate, onDrillRecords }: ViewSwitcherProps) {
  const onDrillRecordsFn = onDrillRecords
    ? (_sel: unknown, records: Row[]) => onDrillRecords(records)
    : undefined;
  const { valid, errors } = validateViewDefinition(definition, entity);
  if (!valid) {
    return (
      <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
        <p className="mb-1 font-medium text-foreground">This view needs configuration:</p>
        <ul className="list-inside list-disc">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </div>
    );
  }

  const c = definition.config;
  const update = onUpdate ?? (() => Promise.resolve());

  switch (definition.kind) {
    case "kanban":
      return (
        <KanbanView
          rows={rows}
          groupField={s(c, "groupField")!}
          order={Array.isArray(c.order) ? (c.order as string[]) : undefined}
          titleField={s(c, "titleField")}
          onMove={(id, patch) => update(id, patch)}
        />
      );
    case "calendar": {
      const now = new Date();
      return (
        <CalendarView
          rows={rows}
          dateField={s(c, "dateField")!}
          titleField={s(c, "titleField")}
          year={typeof c.year === "number" ? c.year : now.getFullYear()}
          month={typeof c.month === "number" ? c.month : now.getMonth()}
          onReschedule={(id, patch) => update(id, patch)}
        />
      );
    }
    case "tree":
      return <HierarchyView rows={rows} parentField={s(c, "parentField")!} labelField={s(c, "labelField")} layout="tree" />;
    case "org_chart":
      return <HierarchyView rows={rows} parentField={s(c, "parentField")!} labelField={s(c, "labelField")} layout="org" />;
    case "timeline":
      return (
        <TimelineView
          rows={rows}
          dateField={s(c, "dateField")!}
          titleField={s(c, "titleField")}
          dir={(c.dir as SortDir) ?? "desc"}
        />
      );
    case "map":
      return <MapView rows={rows} latField={s(c, "latField")!} lngField={s(c, "lngField")!} labelField={s(c, "labelField")} />;
    case "pivot":
      return (
        <PivotView
          rows={rows}
          rowField={s(c, "rowField")!}
          colField={s(c, "colField")!}
          valueField={s(c, "valueField") ?? null}
          agg={c.agg as Agg}
        />
      );
    case "chart":
      return (
        <ChartRenderer
          rows={rows}
          spec={{
            type: (c.chartType as ChartTypeName) ?? "bar",
            x: { field: s(c, "groupField")! },
            series: s(c, "seriesField") ? { field: s(c, "seriesField")! } : undefined,
            valueField: s(c, "valueField") ?? null,
            agg: c.agg as Agg,
            drilldown: { enabled: true, entitySlug: entity.slug },
          }}
          onDrill={onDrillRecordsFn}
        />
      );
    case "gantt":
      return (
        <GanttView
          rows={rows}
          config={{
            startField: s(c, "startField")!,
            endField: s(c, "endField")!,
            labelField: s(c, "labelField"),
            progressField: s(c, "progressField") ?? null,
            dependencyField: s(c, "dependencyField") ?? null,
          }}
        />
      );
    case "dashboard":
      return <DashboardView rows={rows} widgets={(c.widgets as DashboardWidgetDef[]) ?? []} />;
    default:
      return null;
  }
}
