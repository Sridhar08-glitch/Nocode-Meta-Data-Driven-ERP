"use client";

import { buildForest, flattenForest } from "@/lib/views/hierarchy";
import { type Row, rowId, toText, type TreeNode } from "@/lib/views/types";
import { cn } from "@/lib/utils";

export interface HierarchyViewProps {
  rows: Row[];
  parentField: string;
  labelField?: string;
  /** "tree" = indented list (Tree view); "org" = stacked boxes (Org Chart). */
  layout?: "tree" | "org";
}

const label = (row: Row, labelField?: string) =>
  toText(labelField ? row[labelField] : row.id) || rowId(row);

/** Tree / Org Chart over a self-referencing parent (manager) field (Phase F2.1). */
export function HierarchyView({ rows, parentField, labelField, layout = "tree" }: HierarchyViewProps) {
  const forest = buildForest(rows, parentField);
  if (flattenForest(forest).length === 0) {
    return <p className="text-sm text-muted-foreground">No records to chart.</p>;
  }

  if (layout === "org") {
    return (
      <div className="space-y-4" aria-label="Org chart">
        {forest.map((root) => (
          <OrgNode key={rowId(root.row)} node={root} labelField={labelField} />
        ))}
      </div>
    );
  }

  const flat = flattenForest(forest);
  return (
    <ul aria-label="Tree" className="space-y-0.5 text-sm">
      {flat.map((node) => (
        <li
          key={rowId(node.row)}
          style={{ paddingLeft: `${node.depth * 16}px` }}
          className="flex items-center gap-1 py-0.5"
        >
          <span aria-hidden className="text-muted-foreground">
            {node.children.length ? "▸" : "•"}
          </span>
          <span>{label(node.row, labelField)}</span>
        </li>
      ))}
    </ul>
  );
}

function OrgNode({ node, labelField }: { node: TreeNode; labelField?: string }) {
  return (
    <div className="flex flex-col items-center">
      <div className={cn("rounded-md border bg-background px-3 py-1.5 text-sm shadow-sm")}>
        {label(node.row, labelField)}
      </div>
      {node.children.length > 0 && (
        <div className="mt-2 flex flex-wrap items-start justify-center gap-3 border-t pt-2">
          {node.children.map((c) => (
            <OrgNode key={rowId(c.row)} node={c} labelField={labelField} />
          ))}
        </div>
      )}
    </div>
  );
}
