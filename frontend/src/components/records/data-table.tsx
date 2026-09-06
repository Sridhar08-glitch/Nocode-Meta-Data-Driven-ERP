"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCell, type ListColumn } from "@/lib/records/columns";
import { cn } from "@/lib/utils";

export interface SortState {
  field: string;
  direction: "asc" | "desc";
}

export interface DataTableProps {
  columns: ListColumn[];
  rows: Record<string, unknown>[];
  sort: SortState | null;
  onSort: (field: string) => void;
  selected: Set<string>;
  onToggleRow: (id: string) => void;
  onToggleAll: () => void;
  onRowClick?: (id: string) => void;
}

const rowId = (r: Record<string, unknown>) => String(r.id);

export function DataTable({
  columns,
  rows,
  sort,
  onSort,
  selected,
  onToggleRow,
  onToggleAll,
  onRowClick,
}: DataTableProps) {
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(rowId(r)));

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">
            <Checkbox
              checked={allSelected}
              onCheckedChange={onToggleAll}
              aria-label="Select all rows"
            />
          </TableHead>
          {columns.map((col) => (
            <TableHead key={col.slug}>
              {col.sortable ? (
                <button
                  type="button"
                  onClick={() => onSort(col.slug)}
                  className="flex items-center gap-1 hover:text-foreground"
                >
                  {col.label}
                  {sort?.field === col.slug ? (
                    sort.direction === "asc" ? (
                      <ArrowUp className="size-3.5" />
                    ) : (
                      <ArrowDown className="size-3.5" />
                    )
                  ) : (
                    <ChevronsUpDown className="size-3.5 opacity-40" />
                  )}
                </button>
              ) : (
                col.label
              )}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const id = rowId(row);
          const isSelected = selected.has(id);
          return (
            <TableRow
              key={id}
              data-state={isSelected ? "selected" : undefined}
              className={cn(onRowClick && "cursor-pointer")}
              onClick={() => onRowClick?.(id)}
            >
              <TableCell onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={isSelected}
                  onCheckedChange={() => onToggleRow(id)}
                  aria-label="Select row"
                />
              </TableCell>
              {columns.map((col) => (
                <TableCell key={col.slug}>
                  {formatCell(row[col.slug], { field_type: col.fieldType, name: col.label })}
                </TableCell>
              ))}
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
