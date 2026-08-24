"""
CommentService (PROJECT_HANDBOOK.md §23.2).

Comments are threaded notes on a record. Each create/edit/delete emits a
``comment.*`` domain event on the record's aggregate stream — the
:class:`~apps.activity.projectors` wildcard projector turns those into
``ActivityEntry`` rows, and ``@[uuid]`` mentions fan out to in-app notifications
via :class:`~apps.notifications.services.NotificationService`.
"""
from __future__ import annotations

import re
import uuid

from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import Comment

_MENTION_RE = re.compile(r"@\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                         r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]")


class CommentError(Exception):  # noqa: N818 — domain error
    pass


class CommentPermissionError(Exception):  # noqa: N818
    pass


def extract_mentions(body: str) -> list[str]:
    """Return unique member UUIDs referenced as ``@[uuid]`` in *body*."""
    seen, out = set(), []
    for m in _MENTION_RE.findall(body or ""):
        low = m.lower()
        if low not in seen:
            seen.add(low)
            out.append(m)
    return out


def _emit(workspace_id, record_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    rid = uuid.UUID(str(record_id))
    version = DomainEvent.objects.filter(aggregate_id=rid).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="record", aggregate_id=rid, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _resolve_entity(workspace_id, entity_slug):
    try:
        return SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=entity_slug)
    except EntityNotFoundError as exc:
        raise CommentError(str(exc)) from exc


def _notify_mentions(*, workspace_id, entity_slug, record_id, mention_ids, actor_id, body):
    from apps.notifications.services import NotificationService
    for mid in mention_ids:
        if str(mid) == str(actor_id):
            continue  # don't notify self-mentions
        NotificationService.send(
            recipient_id=mid, recipient_type="member", template_slug="comment_mention",
            context={"event_type": "comment_mention", "entity_slug": entity_slug,
                     "record_id": str(record_id), "actor_id": str(actor_id) if actor_id else "",
                     "subject": "You were mentioned", "body": body[:500]},
            workspace_id=workspace_id, channels=["in_app"])


class CommentService:
    @staticmethod
    def create_comment(*, record_id, entity_slug, body, author_id,
                       author_type="member", parent_id=None, workspace_id,
                       body_format="markdown") -> Comment:
        if not body or not body.strip():
            raise CommentError("Comment body is required")
        entity = _resolve_entity(workspace_id, entity_slug)
        if parent_id:
            parent = Comment.objects.filter(
                id=parent_id, workspace_id=workspace_id, record_id=record_id).first()
            if parent is None:
                raise CommentError("Parent comment does not belong to this record")
        mention_ids = extract_mentions(body)
        comment = Comment.objects.create(
            workspace_id=workspace_id, entity_id=entity.id, record_id=record_id,
            author_id=author_id, author_type=author_type, parent_id=parent_id,
            body=body, body_format=body_format,
            mentions=[{"type": "member", "id": m} for m in mention_ids])
        _emit(workspace_id, record_id, "comment.created", {
            "comment_id": str(comment.id), "entity_slug": entity_slug,
            "entity_id": str(entity.id), "author_id": str(author_id),
            "parent_id": str(parent_id) if parent_id else None,
            "body": body[:1000]}, author_id)
        _notify_mentions(workspace_id=workspace_id, entity_slug=entity_slug,
                         record_id=record_id, mention_ids=mention_ids,
                         actor_id=author_id, body=body)
        return comment

    @staticmethod
    def edit_comment(comment_id, body, editor_id) -> Comment:
        comment = Comment.objects.filter(id=comment_id).first()
        if comment is None:
            raise CommentError("Comment not found")
        if str(comment.author_id) != str(editor_id):
            raise CommentPermissionError("Only the author can edit this comment")
        if not body or not body.strip():
            raise CommentError("Comment body is required")
        comment.body = body
        comment.is_edited = True
        comment.mentions = [{"type": "member", "id": m} for m in extract_mentions(body)]
        comment.save(update_fields=["body", "is_edited", "mentions", "updated_at"])
        _emit(comment.workspace_id, comment.record_id, "comment.updated",
              {"comment_id": str(comment.id), "entity_id": str(comment.entity_id)}, editor_id)
        return comment

    @staticmethod
    def delete_comment(comment_id, actor_id) -> Comment:
        comment = Comment.objects.filter(id=comment_id).first()
        if comment is None:
            raise CommentError("Comment not found")
        comment.is_deleted = True
        comment.deleted_at = timezone.now()
        comment.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        # children are intentionally orphaned, not deleted
        _emit(comment.workspace_id, comment.record_id, "comment.deleted",
              {"comment_id": str(comment.id), "entity_id": str(comment.entity_id)}, actor_id)
        return comment

    @staticmethod
    def set_pinned(comment_id, workspace_id, pinned: bool) -> Comment:
        comment = Comment.objects.filter(id=comment_id, workspace_id=workspace_id).first()
        if comment is None:
            raise CommentError("Comment not found")
        comment.is_pinned = pinned
        comment.save(update_fields=["is_pinned", "updated_at"])
        return comment

    @staticmethod
    def list_for_record(*, workspace_id, record_id, include_deleted=False):
        qs = Comment.objects.filter(workspace_id=workspace_id, record_id=record_id)
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs.order_by("-is_pinned", "created_at")
