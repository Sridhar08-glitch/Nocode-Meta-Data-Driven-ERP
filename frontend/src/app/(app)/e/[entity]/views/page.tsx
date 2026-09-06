"use client";

import { useMemo, useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, PermissionDeniedState } from "@/components/ui/states";
import { ViewSwitcher } from "@/components/views/view-switcher";
import { useEntityMeta } from "@/lib/metadata/hooks";
import { useRecords, useUpdateRecord } from "@/lib/records/hooks";
import { defaultViewConfig } from "@/lib/views/engine";
import type { ViewKind } from "@/lib/views/types";

const VIEW_KINDS: { value: ViewKind; label: string }[] = [
  { value: "kanban", label: "Kanban" },
  { value: "calendar", label: "Calendar" },
  { value: "timeline", label: "Timeline" },
  { value: "tree", label: "Tree" },
  { value: "org_chart", label: "Org chart" },
  { value: "map", label: "Map" },
  { value: "pivot", label: "Pivot" },
  { value: "gantt", label: "Gantt" },
  { value: "chart", label: "Chart" },
  { value: "dashboard", label: "Dashboard" },
];

/** Alternate views for an entity (Phase F2.1) — every kind reads the same records + metadata. */
export default function EntityViewsPage({ params }: { params: { entity: string } }) {
  const slug = params.entity;
  const { entity, isLoading, isError } = useEntityMeta(slug);
  const [kind, setKind] = useState<ViewKind>("kanban");
  const records = useRecords(slug, { limit: 200 });
  const update = useUpdateRecord(slug);

  const config = useMemo(() => (entity ? defaultViewConfig(kind, entity) : {}), [entity, kind]);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError || !entity) return <ErrorState title="Entity not found" />;
  if (entity.can_read === false) {
    return <PermissionDeniedState description={`You can't view ${entity.plural_name}.`} />;
  }

  const rows = records.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{entity.plural_name}</h1>
        <Select value={kind} onValueChange={(v) => setKind(v as ViewKind)}>
          <SelectTrigger aria-label="View type" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VIEW_KINDS.map((k) => (
              <SelectItem key={k.value} value={k.value}>
                {k.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {records.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : records.isError ? (
        <ErrorState title="Couldn't load records" />
      ) : (
        <ViewSwitcher
          definition={{ kind, config }}
          rows={rows}
          entity={entity}
          onUpdate={(id, data) => update.mutateAsync({ id, data })}
        />
      )}
    </div>
  );
}
