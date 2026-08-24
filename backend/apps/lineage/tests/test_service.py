"""LineageService (PROJECT_HANDBOOK.md §31.2 / §31.5)."""
import uuid

import pytest

from apps.lineage.models import LineageEdge, LineageNode
from apps.lineage.services import LineageService


@pytest.mark.django_db
class TestNodes:
    def test_ensure_node_idempotent(self, ws):
        oid = uuid.uuid4()
        n1 = LineageService.ensure_node(ws.id, "entity", oid, display_name="Lead")
        n2 = LineageService.ensure_node(ws.id, "entity", oid, display_name="Lead v2")
        assert n1.id == n2.id
        assert LineageNode.objects.filter(workspace_id=ws.id).count() == 1
        assert LineageNode.objects.get(id=n1.id).display_name == "Lead v2"

    def test_record_edge_creates_nodes_and_edge(self, ws):
        a, b = uuid.uuid4(), uuid.uuid4()
        LineageService.record_edge(ws.id, "entity", a, "report", b, "reads")
        assert LineageNode.objects.filter(workspace_id=ws.id).count() == 2
        assert LineageEdge.objects.filter(workspace_id=ws.id).count() == 1
        # idempotent
        LineageService.record_edge(ws.id, "entity", a, "report", b, "reads")
        assert LineageEdge.objects.filter(workspace_id=ws.id).count() == 1


@pytest.mark.django_db
class TestTraversal:
    def _chain(self, ws):
        # A -> B -> C -> D
        ids = [uuid.uuid4() for _ in range(4)]
        nodes = [LineageService.ensure_node(ws.id, "entity", oid, display_name=f"N{i}")
                 for i, oid in enumerate(ids)]
        for s, t in zip(nodes, nodes[1:], strict=False):
            LineageService.record_edge(ws.id, "entity", s.object_id, "entity", t.object_id, "writes")
        return nodes

    def test_downstream(self, ws):
        nodes = self._chain(ws)
        graph = LineageService.get_downstream(nodes[0].id, ws.id, max_depth=5)
        names = {n["display_name"] for n in graph["nodes"]}
        assert names == {"N0", "N1", "N2", "N3"}

    def test_upstream(self, ws):
        nodes = self._chain(ws)
        graph = LineageService.get_upstream(nodes[3].id, ws.id, max_depth=5)
        names = {n["display_name"] for n in graph["nodes"]}
        assert names == {"N0", "N1", "N2", "N3"}

    def test_max_depth_bounds_traversal(self, ws):
        nodes = self._chain(ws)
        graph = LineageService.get_downstream(nodes[0].id, ws.id, max_depth=1)
        names = {n["display_name"] for n in graph["nodes"]}
        assert names == {"N0", "N1"}   # does not reach N2/N3
