"""
LineageService (PROJECT_HANDBOOK.md §31.2).

Maintains a directed data-lineage graph (``LineageNode`` + ``LineageEdge``) and
traverses it upstream/downstream with a depth bound. Nodes/edges are upserted
idempotently so integration points can call freely.
"""
from __future__ import annotations

from .models import LineageEdge, LineageNode


class LineageService:
    @staticmethod
    def ensure_node(workspace_id, node_type, object_id, display_name="",
                    object_slug="", metadata=None) -> LineageNode:
        # Only overwrite optional descriptors when a value is actually supplied,
        # so a bare ensure_node() (e.g. from record_edge) never blanks them out.
        defaults = {}
        if display_name:
            defaults["display_name"] = display_name
        if object_slug:
            defaults["object_slug"] = object_slug
        if metadata is not None:
            defaults["metadata"] = metadata
        node, _ = LineageNode.objects.update_or_create(
            workspace_id=workspace_id, node_type=node_type, object_id=object_id,
            defaults=defaults)
        return node

    @staticmethod
    def record_edge(workspace_id, source_type, source_id, target_type, target_id,
                    edge_type, metadata=None) -> LineageEdge:
        source = LineageService.ensure_node(workspace_id, source_type, source_id)
        target = LineageService.ensure_node(workspace_id, target_type, target_id)
        edge, _ = LineageEdge.objects.update_or_create(
            workspace_id=workspace_id, source_node_id=source.id, target_node_id=target.id,
            edge_type=edge_type,
            defaults={"metadata": metadata or {}})
        return edge

    @staticmethod
    def _traverse(node_id, workspace_id, max_depth, *, forward) -> dict:
        visited_nodes, visited_edges = set(), set()
        frontier = [(node_id, 0)]
        while frontier:
            current, depth = frontier.pop()
            if current in visited_nodes or depth > max_depth:
                continue
            visited_nodes.add(current)
            if depth >= max_depth:
                continue
            if forward:
                edges = LineageEdge.objects.filter(
                    workspace_id=workspace_id, source_node_id=current)
            else:
                edges = LineageEdge.objects.filter(
                    workspace_id=workspace_id, target_node_id=current)
            for edge in edges:
                visited_edges.add(edge.id)
                nxt = edge.target_node_id if forward else edge.source_node_id
                frontier.append((nxt, depth + 1))
        nodes = LineageNode.objects.filter(workspace_id=workspace_id, id__in=visited_nodes)
        edges = LineageEdge.objects.filter(workspace_id=workspace_id, id__in=visited_edges)
        return {
            "nodes": [LineageService._node_dict(n) for n in nodes],
            "edges": [LineageService._edge_dict(e) for e in edges],
        }

    @staticmethod
    def get_upstream(node_id, workspace_id, max_depth=5) -> dict:
        return LineageService._traverse(node_id, workspace_id, max_depth, forward=False)

    @staticmethod
    def get_downstream(node_id, workspace_id, max_depth=5) -> dict:
        return LineageService._traverse(node_id, workspace_id, max_depth, forward=True)

    @staticmethod
    def list_nodes(workspace_id, node_type=None):
        qs = LineageNode.objects.filter(workspace_id=workspace_id)
        if node_type:
            qs = qs.filter(node_type=node_type)
        return qs.order_by("node_type", "display_name")

    @staticmethod
    def _node_dict(n) -> dict:
        return {"id": str(n.id), "node_type": n.node_type, "object_id": str(n.object_id),
                "object_slug": n.object_slug, "display_name": n.display_name,
                "metadata": n.metadata}

    @staticmethod
    def _edge_dict(e) -> dict:
        return {"id": str(e.id), "source_node_id": str(e.source_node_id),
                "target_node_id": str(e.target_node_id), "edge_type": e.edge_type,
                "metadata": e.metadata}
