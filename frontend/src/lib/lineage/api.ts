/**
 * Data Lineage client (Phase F3.3) — node listing + upstream/downstream graph traversal over
 * `/api/v1/lineage/` (backend Phase 1.22). Read-only, workspace-scoped, depth-bounded (max 10).
 */
import { apiGet } from "@/lib/api/request";

export interface LineageNode {
  id: string;
  node_type: string;
  object_id: string;
  object_slug: string;
  display_name: string;
}
export interface LineageEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
}
export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}
export interface NodeList {
  results: LineageNode[];
  count: number;
}

const L = "/api/v1/lineage";

export const lineageApi = {
  listNodes: (nodeType?: string) =>
    apiGet<NodeList>(`${L}/nodes/${nodeType ? `?node_type=${encodeURIComponent(nodeType)}` : ""}`),
  upstream: (id: string, maxDepth = 5) => apiGet<LineageGraph>(`${L}/nodes/${id}/upstream/?max_depth=${maxDepth}`),
  downstream: (id: string, maxDepth = 5) => apiGet<LineageGraph>(`${L}/nodes/${id}/downstream/?max_depth=${maxDepth}`),
};
