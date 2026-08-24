"""
Search REST API (PROJECT_HANDBOOK.md §26.3).

Workspace-scoped full-text search + SearchIndex / SavedSearch / RecentSearch
management. Search reads never cross workspaces (every query is filtered by
``workspace_id``).
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import RecentSearch, SavedSearch, SearchIndex
from .serializers import (
    RecentSearchSerializer,
    SavedSearchSerializer,
    SearchIndexSerializer,
)
from .services import SearchService

_WRITE_ROLES = {"owner", "admin", "member"}


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


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


class SearchView(APIView):
    def get(self, request):
        member = _member(request)
        ws = _ws(request)
        query = request.query_params.get("q", "")
        entity_slugs = None
        if request.query_params.get("entity"):
            entity_slugs = [s for s in request.query_params["entity"].split(",") if s]
        try:
            limit = min(int(request.query_params.get("limit", 25)), 100)
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("limit/offset must be integers") from exc
        result = SearchService.search(query=query, workspace_id=ws,
                                      entity_slugs=entity_slugs, limit=limit, offset=offset)
        if query.strip():
            SearchService.log_recent_search(
                member_id=member.user_id, workspace_id=ws, query=query,
                entity_slug=entity_slugs[0] if entity_slugs else None,
                result_count=result["total"])
        return Response(result)


class IndexListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = SearchIndex.objects.filter(workspace_id=_ws(request))
        return Response({"results": SearchIndexSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ws = _ws(request)
        slug = request.data.get("entity_slug")
        if not slug:
            raise ValidationError("entity_slug is required")
        try:
            entity = SchemaRegistryService.get_entity(workspace_id=ws, slug=slug)
        except EntityNotFoundError as exc:
            raise NotFound(str(exc)) from exc
        index = SearchService.create_index(
            entity=entity, workspace_id=ws,
            indexed_field_slugs=request.data.get("indexed_field_slugs", []),
            field_weights=request.data.get("field_weights", {}))
        return Response(SearchIndexSerializer(index).data, status=status.HTTP_201_CREATED)


class IndexDetailView(APIView):
    def _get(self, request, pk):
        idx = SearchIndex.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if idx is None:
            raise NotFound("Index not found")
        return idx

    def get(self, request, pk):
        _member(request)
        return Response(SearchIndexSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        idx = self._get(request, pk)
        for field in ("indexed_field_slugs", "field_weights"):
            if field in request.data:
                setattr(idx, field, request.data[field])
        idx.save()
        return Response(SearchIndexSerializer(idx).data)

    def delete(self, request, pk):
        _require_write(request)
        self._get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IndexReindexView(APIView):
    def post(self, request, pk):
        _require_write(request)
        idx = SearchIndex.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if idx is None:
            raise NotFound("Index not found")
        from .tasks import reindex_entity
        reindex_entity.delay(str(idx.id))
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class SavedSearchListCreateView(APIView):
    def get(self, request):
        member = _member(request)
        from django.db.models import Q
        qs = SavedSearch.objects.filter(workspace_id=_ws(request)).filter(
            Q(created_by=member.user_id) | Q(is_shared=True)).order_by("name")
        return Response({"results": SavedSearchSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        member = _member(request)
        ser = SavedSearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request), created_by=member.user_id)
        return Response(SavedSearchSerializer(obj).data, status=status.HTTP_201_CREATED)


class SavedSearchDetailView(APIView):
    def _get(self, request, pk):
        obj = SavedSearch.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Saved search not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(SavedSearchSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        member = _member(request)
        obj = self._get(request, pk)
        if str(obj.created_by) != str(member.user_id):
            raise PermissionDenied("Only the owner can edit this saved search")
        ser = SavedSearchSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(SavedSearchSerializer(obj).data)

    def delete(self, request, pk):
        member = _member(request)
        obj = self._get(request, pk)
        if str(obj.created_by) != str(member.user_id):
            raise PermissionDenied("Only the owner can delete this saved search")
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecentSearchView(APIView):
    def get(self, request):
        member = _member(request)
        qs = RecentSearch.objects.filter(
            workspace_id=_ws(request), member_id=member.user_id).order_by("-searched_at")[:20]
        return Response({"results": RecentSearchSerializer(qs, many=True).data, "count": len(qs)})

    def delete(self, request):
        member = _member(request)
        n, _ = RecentSearch.objects.filter(
            workspace_id=_ws(request), member_id=member.user_id).delete()
        return Response({"cleared": n})
