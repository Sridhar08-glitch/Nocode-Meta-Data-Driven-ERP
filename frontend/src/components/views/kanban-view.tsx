"use client";

import { useEffect, useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { UNASSIGNED } from "@/lib/views/grouping";
import { applyMove, kanbanColumns, movePatch } from "@/lib/views/kanban";
import { type Row, rowId, toText } from "@/lib/views/types";

export interface KanbanViewProps {
  rows: Row[];
  groupField: string;
  /** Column order (e.g. a select field's option values). */
  order?: string[];
  titleField?: string;
  /** Persist a card move; rejecting triggers a rollback. */
  onMove: (id: string, patch: Record<string, string>) => Promise<unknown>;
}

/** Kanban board with optimistic card moves and rollback on mutation failure (Phase F2.1). */
export function KanbanView({ rows, groupField, order, titleField, onMove }: KanbanViewProps) {
  // local optimistic copy; resyncs when the upstream rows change
  const [local, setLocal] = useState<Row[]>(rows);
  useEffect(() => setLocal(rows), [rows]);

  const columns = kanbanColumns(local, groupField, order);

  async function move(id: string, targetKey: string) {
    const prev = local;
    setLocal((cur) => applyMove(cur, id, groupField, targetKey)); // optimistic
    try {
      await onMove(id, movePatch(groupField, targetKey));
    } catch (err) {
      setLocal(prev); // rollback
      toast.error(err instanceof ApiError ? err.message : "Couldn't move card");
    }
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-2" role="list" aria-label="Kanban board">
      {columns.map((col) => (
        <section
          key={col.key}
          role="listitem"
          aria-label={`${col.label} (${col.records.length})`}
          className="w-64 shrink-0 rounded-md border bg-muted/30 p-2"
        >
          <h3 className="mb-2 px-1 text-sm font-medium">
            {col.label} <span className="text-muted-foreground">{col.records.length}</span>
          </h3>
          <ul className="space-y-2">
            {col.records.map((row) => {
              const id = rowId(row);
              const title = toText(titleField ? row[titleField] : row.id) || id;
              return (
                <li key={id} className="rounded-md border bg-background p-2 text-sm shadow-sm">
                  <div className="mb-1 truncate font-medium">{title}</div>
                  <Select value={col.key} onValueChange={(v) => move(id, v)}>
                    <SelectTrigger aria-label={`Move ${title}`} className="h-7 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {columns
                        .filter((c) => c.key !== UNASSIGNED)
                        .map((c) => (
                          <SelectItem key={c.key} value={c.key}>
                            {c.label}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </li>
              );
            })}
            {col.records.length === 0 && (
              <li className="px-1 py-2 text-xs text-muted-foreground">Empty</li>
            )}
          </ul>
        </section>
      ))}
    </div>
  );
}
