"""CommentService (PROJECT_HANDBOOK.md §23.2 / §23.4)."""
import uuid

import pytest

from apps.activity.services import (
    CommentError,
    CommentPermissionError,
    CommentService,
    extract_mentions,
)
from apps.eventstore.models import DomainEvent
from apps.notifications.models import Notification


def test_extract_mentions():
    a = uuid.uuid4()
    b = uuid.uuid4()
    body = f"hi @[{a}] and @[{b}] and again @[{a}]"
    out = extract_mentions(body)
    assert out == [str(a), str(b)]


@pytest.mark.django_db
class TestComments:
    def _rec(self):
        return uuid.uuid4()

    def test_create_emits_event(self, ws, lead, user):
        rid = self._rec()
        c = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="Hello", author_id=user.id,
            workspace_id=ws.id)
        assert c.entity_id == lead.id
        assert DomainEvent.objects.filter(
            aggregate_id=rid, event_type="comment.created").exists()

    def test_mention_dispatches_notification(self, ws, lead, user):
        mentioned = uuid.uuid4()
        rid = self._rec()
        CommentService.create_comment(
            record_id=rid, entity_slug="lead", body=f"ping @[{mentioned}]",
            author_id=user.id, workspace_id=ws.id)
        assert Notification.objects.filter(
            workspace_id=ws.id, recipient_id=mentioned, channel="in_app").exists()

    def test_self_mention_not_notified(self, ws, lead, user):
        rid = self._rec()
        CommentService.create_comment(
            record_id=rid, entity_slug="lead", body=f"note @[{user.id}]",
            author_id=user.id, workspace_id=ws.id)
        assert not Notification.objects.filter(recipient_id=user.id).exists()

    def test_reply_parent_validation(self, ws, lead, user):
        rid = self._rec()
        parent = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="root", author_id=user.id,
            workspace_id=ws.id)
        reply = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="child", author_id=user.id,
            workspace_id=ws.id, parent_id=parent.id)
        assert reply.parent_id == parent.id
        with pytest.raises(CommentError):
            CommentService.create_comment(
                record_id=self._rec(), entity_slug="lead", body="x",
                author_id=user.id, workspace_id=ws.id, parent_id=parent.id)

    def test_edit_only_author(self, ws, lead, user):
        rid = self._rec()
        c = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="orig", author_id=user.id,
            workspace_id=ws.id)
        CommentService.edit_comment(c.id, "updated", user.id)
        c.refresh_from_db()
        assert c.body == "updated" and c.is_edited
        with pytest.raises(CommentPermissionError):
            CommentService.edit_comment(c.id, "hacked", uuid.uuid4())

    def test_delete_soft_and_orphans_children(self, ws, lead, user):
        rid = self._rec()
        parent = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="p", author_id=user.id,
            workspace_id=ws.id)
        child = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="c", author_id=user.id,
            workspace_id=ws.id, parent_id=parent.id)
        CommentService.delete_comment(parent.id, user.id)
        parent.refresh_from_db()
        child.refresh_from_db()
        assert parent.is_deleted and parent.deleted_at is not None
        assert not child.is_deleted   # child orphaned, not deleted

    def test_set_pinned(self, ws, lead, user):
        rid = self._rec()
        c = CommentService.create_comment(
            record_id=rid, entity_slug="lead", body="p", author_id=user.id,
            workspace_id=ws.id)
        CommentService.set_pinned(c.id, ws.id, True)
        c.refresh_from_db()
        assert c.is_pinned

    def test_empty_body_rejected(self, ws, lead, user):
        with pytest.raises(CommentError):
            CommentService.create_comment(
                record_id=self._rec(), entity_slug="lead", body="  ",
                author_id=user.id, workspace_id=ws.id)
