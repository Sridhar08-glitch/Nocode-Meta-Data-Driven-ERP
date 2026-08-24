"""NotificationService.send + read/count (PROJECT_HANDBOOK.md §22.2 / §22.6)."""
import pytest

from apps.notifications.models import (
    Notification,
    NotificationPreference,
)
from apps.notifications.services import NotificationService


@pytest.mark.django_db
class TestSend:
    def test_send_per_channel_templates(self, ws, user, template):
        template(slug="alert", channel="in_app", body="in ${actor_name}")
        template(slug="alert", channel="email", body="email ${actor_name}")
        out = NotificationService.send(
            recipient_id=user.id, template_slug="alert",
            context={"actor_name": "Ada"}, workspace_id=ws.id)
        channels = {n.channel for n in out}
        assert channels == {"in_app", "email"}
        assert Notification.objects.filter(workspace_id=ws.id, recipient_id=user.id).count() == 2

    def test_channels_override_filters(self, ws, user, template):
        template(slug="alert", channel="in_app")
        template(slug="alert", channel="email")
        out = NotificationService.send(
            recipient_id=user.id, template_slug="alert", context={"actor_name": "A"},
            workspace_id=ws.id, channels=["email"])
        assert [n.channel for n in out] == ["email"]

    def test_preference_disabled_skips_channel(self, ws, user, member, template):
        template(slug="alert", channel="in_app")
        NotificationPreference.objects.create(
            workspace_id=ws.id, member_id=user.id, event_type="lead_assigned",
            channel="in_app", enabled=False)
        out = NotificationService.send(
            recipient_id=user.id, template_slug="alert",
            context={"actor_name": "A", "event_type": "lead_assigned"},
            workspace_id=ws.id)
        assert out == []

    def test_idempotency_dedup(self, ws, user, template):
        template(slug="alert", channel="in_app")
        ctx = {"actor_name": "A", "idempotency_key": "evt-1"}
        first = NotificationService.send(recipient_id=user.id, template_slug="alert",
                                         context=ctx, workspace_id=ws.id)
        second = NotificationService.send(recipient_id=user.id, template_slug="alert",
                                          context=ctx, workspace_id=ws.id)
        assert len(first) == 1
        assert second == []

    def test_fallback_without_template(self, ws, user):
        out = NotificationService.send(
            recipient_id=user.id, template_slug="missing",
            context={"subject": "S", "body": "B"}, workspace_id=ws.id,
            channels=["in_app"])
        assert len(out) == 1
        assert out[0].body == "B"


@pytest.mark.django_db
class TestReadAndCount:
    def _mk(self, ws, recipient):
        return Notification.objects.create(
            workspace_id=ws.id, recipient_id=recipient, channel="in_app",
            status="sent", body="x")

    def test_mark_read(self, ws, user):
        n = self._mk(ws, user.id)
        NotificationService.mark_read(n.id, user.id)
        n.refresh_from_db()
        assert n.read_at is not None
        assert n.status == "read"

    def test_unread_count_and_mark_all(self, ws, user):
        for _ in range(3):
            self._mk(ws, user.id)
        assert NotificationService.get_unread_count(user.id, ws.id) == 3
        updated = NotificationService.mark_all_read(user.id, ws.id)
        assert updated == 3
        assert NotificationService.get_unread_count(user.id, ws.id) == 0

    def test_mark_all_read_scoped_to_caller_and_workspace(self, ws, user):
        import uuid

        from apps.tenancy.models import Workspace
        other_ws = Workspace.objects.create(name="O", slug="o", is_active=True)
        self._mk(ws, user.id)                 # mine, this ws
        self._mk(ws, uuid.uuid4())            # someone else, this ws
        self._mk(other_ws, user.id)           # mine, other ws
        updated = NotificationService.mark_all_read(user.id, ws.id)
        assert updated == 1
