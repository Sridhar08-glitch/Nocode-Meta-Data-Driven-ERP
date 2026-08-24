"""
Data Lineage REST API (PROJECT_HANDBOOK.md §31.3) at /api/v1/lineage/.

Read-only graph traversal (upstream/downstream) + node listing, workspace-scoped.
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LineageNode
from .services import LineageService


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _node(request, pk) -> LineageNode:
    n = LineageNode.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if n is None:
        raise NotFound("Lineage node not found")
    return n


def _depth(request) -> int:
    try:
        return min(int(request.query_params.get("max_depth", 5)), 10)
    except (TypeError, ValueError) as exc:
        raise ValidationError("max_depth must be an integer") from exc


class NodeListView(APIView):
    def get(self, request):
        _member(request)
        nodes = LineageService.list_nodes(_ws(request), request.query_params.get("node_type"))
        return Response({"results": [LineageService._node_dict(n) for n in nodes],
                         "count": nodes.count()})


class NodeUpstreamView(APIView):
    def get(self, request, pk):
        _member(request)
        node = _node(request, pk)
        return Response(LineageService.get_upstream(node.id, _ws(request), _depth(request)))


class NodeDownstreamView(APIView):
    def get(self, request, pk):
        _member(request)
        node = _node(request, pk)
        return Response(LineageService.get_downstream(node.id, _ws(request), _depth(request)))
