/**
 * Hierarchy (Phase F2.1) — parent→children forests for Tree (generic parent field) and Org Chart
 * (manager field). Cycle-protected: any node whose parent chain loops becomes a root. Pure.
 */
import { type Row, rowId, toText, type TreeNode } from "./types";

export function buildForest(rows: Row[], parentField: string): TreeNode[] {
  const nodes = new Map<string, TreeNode>();
  const parentOf = new Map<string, string>();
  for (const row of rows) {
    const id = rowId(row);
    nodes.set(id, { row, children: [], depth: 0 });
    const p = toText(row[parentField]);
    if (p && p !== id) parentOf.set(id, p);
  }

  const loops = (id: string): boolean => {
    const seen = new Set<string>();
    let cur = parentOf.get(id);
    while (cur) {
      if (cur === id || seen.has(cur)) return true;
      seen.add(cur);
      cur = parentOf.get(cur);
    }
    return false;
  };

  const roots: TreeNode[] = [];
  for (const row of rows) {
    const id = rowId(row);
    const p = parentOf.get(id);
    const parent = p ? nodes.get(p) : undefined;
    if (parent && !loops(id)) parent.children.push(nodes.get(id)!);
    else roots.push(nodes.get(id)!);
  }

  // assign depths
  const setDepth = (node: TreeNode, depth: number) => {
    node.depth = depth;
    for (const c of node.children) setDepth(c, depth + 1);
  };
  for (const r of roots) setDepth(r, 0);
  return roots;
}

/** Flatten a forest depth-first (useful for indented tree rendering + counting). */
export function flattenForest(roots: TreeNode[]): TreeNode[] {
  const out: TreeNode[] = [];
  const walk = (n: TreeNode) => {
    out.push(n);
    for (const c of n.children) walk(c);
  };
  for (const r of roots) walk(r);
  return out;
}
