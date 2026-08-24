"""
Activity feed + Comments API (PROJECT_HANDBOOK.md §23.3).

Per-record endpoints are nested under ``/api/v1/data/{entity_slug}/{record_id}/``
(routed from ``apps.records.urls``); the cross-entity feed is at
``/api/v1/activity/feed/``. All endpoints are workspace-scoped and require read
permission on the entity; comment writes require an active membership.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions import services as perm
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import ActivityEntry, Comment
from .serializers import ActivityEntrySerializer, CommentSerializer
from .services import CommentError, CommentPermissionError, CommentService

_ADMIN_ROLES = {"owner", "admin"}


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


def _entity(request, entity_slug):
    try:
        return SchemaRegistryService.get_entity(workspace_id=_ws(request), slug=entity_slug)
    except EntityNotFoundError as exc:
        raise NotFound(str(exc)) from exc


def _require_read(request, entity):
    if not perm.check(_member(request), entity, "read"):
        raise PermissionDenied(f"Not permitted to read {entity.slug}")


def _paginate(request, qs):
    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit/offset must be integers") from exc
    return qs[offset:offset + limit]


class RecordActivityView(APIView):
    def get(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        _require_read(request, entity)
        qs = (ActivityEntry.objects
              .filter(workspace_id=_ws(request), record_id=record_id)
              .order_by("-is_pinned", "-occurred_at"))
        page = _paginate(request, qs)
        return Response({"results": ActivityEntrySerializer(page, many=True).data,
                         "count": qs.count()})


class RecordCommentsView(APIView):
    def get(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        _require_read(request, entity)
        include_deleted = request.query_params.get("include_deleted") in ("1", "true")
        qs = CommentService.list_for_record(
            workspace_id=_ws(request), record_id=record_id, include_deleted=include_deleted)
        return Response({"results": CommentSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        _require_read(request, entity)
        member = _member(request)
        try:
            comment = CommentService.create_comment(
                record_id=record_id, entity_slug=entity_slug,
                body=request.data.get("body", ""), author_id=member.user_id,
                author_type="member", parent_id=request.data.get("parent_id"),
                workspace_id=_ws(request),
                body_format=request.data.get("body_format", "markdown"))
        except CommentError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    def _get(self, request, record_id, comment_id):
        c = Comment.objects.filter(
            id=comment_id, workspace_id=_ws(request), record_id=record_id).first()
        if c is None:
            raise NotFound("Comment not found")
        return c

    def get(self, request, entity_slug, record_id, comment_id):
        _require_read(request, _entity(request, entity_slug))
        return Response(CommentSerializer(self._get(request, record_id, comment_id)).data)

    def patch(self, request, entity_slug, record_id, comment_id):
        _entity(request, entity_slug)
        member = _member(request)
        try:
            comment = CommentService.edit_comment(
                comment_id, request.data.get("body", ""), member.user_id)
        except CommentPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except CommentError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(CommentSerializer(comment).data)

    def delete(self, request, entity_slug, record_id, comment_id):
        _entity(request, entity_slug)
        member = _member(request)
        comment = self._get(request, record_id, comment_id)
        if str(comment.author_id) != str(member.user_id) and \
                getattr(member, "role", "") not in _ADMIN_ROLES:
            raise PermissionDenied("Only the author or an admin can delete this comment")
        CommentService.delete_comment(comment_id, member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentPinView(APIView):
    pinned = True

    def post(self, request, entity_slug, record_id, comment_id):
        _entity(request, entity_slug)
        member = _member(request)
        if getattr(member, "role", "") not in _ADMIN_ROLES:
            raise PermissionDenied("Only an admin can pin comments")
        try:
            comment = CommentService.set_pinned(comment_id, _ws(request), self.pinned)
        except CommentError as exc:
            raise NotFound(str(exc)) from exc
        return Response(CommentSerializer(comment).data)


class CommentUnpinView(CommentPinView):
    pinned = False


class ActivityFeedView(APIView):
    """Cross-entity workspace activity feed for the authenticated member."""
    def get(self, request):
        _member(request)
        qs = ActivityEntry.objects.filter(workspace_id=_ws(request))
        p = request.query_params
        if p.get("entity_slug"):
            entity = _entity(request, p["entity_slug"])
            qs = qs.filter(entity_id=entity.id)
        if p.get("activity_type"):
            qs = qs.filter(activity_type=p["activity_type"])
        if p.get("actor_id"):
            qs = qs.filter(actor_id=p["actor_id"])
        if p.get("date_from"):
            qs = qs.filter(occurred_at__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(occurred_at__lte=p["date_to"])
        qs = qs.order_by("-occurred_at")
        page = _paginate(request, qs)
        return Response({"results": ActivityEntrySerializer(page, many=True).data,
                         "count": qs.count()})
