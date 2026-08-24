"""Channel delivery tasks (PROJECT_HANDBOOK.md §22.3 / §22.6)."""
import contextlib

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core import mail

from apps.notifications import tasks
from apps.notifications.models import Notification


def _notif(ws, recipient, channel="in_app", **kw):
    return Notification.objects.create(
        workspace_id=ws.id, recipient_id=recipient, channel=channel,
        status="pending", subject=kw.pop("subject", "S"), body=kw.pop("body", "B"),
        **kw)


@pytest.mark.django_db
class TestDelivery:
    def test_email_sends_and_marks_sent(self, ws, user):
        n = _notif(ws, user.id, channel="email")
        tasks.deliver_email_notification(str(n.id))
        n.refresh_from_db()
        assert n.status == "sent"
        assert n.sent_at is not None
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]

    def test_in_app_pushes_to_user_group(self, ws, user):
        n = _notif(ws, user.id, channel="in_app")
        layer = get_channel_layer()
        group = f"user_{user.id}_notifications"
        async_to_sync(layer.group_add)(group, "test-chan")
        tasks.deliver_in_app_notification(str(n.id))
        msg = async_to_sync(layer.receive)("test-chan")
        assert msg["type"] == "notification.message"
        assert msg["notification"]["id"] == str(n.id)
        n.refresh_from_db()
        assert n.status == "sent"

    def test_webhook_signs_and_posts(self, ws, user, monkeypatch):
        captured = {}

        def fake_post(url, data, headers, timeout=10):
            captured.update(url=url, data=data, headers=headers)
            return 200

        monkeypatch.setattr(tasks, "_http_post", fake_post)
        monkeypatch.setenv("NOTIFICATION_WEBHOOK_SECRET", "s3cr3t")
        n = _notif(ws, user.id, channel="webhook", action_url="https://hook.example/x")
        tasks.deliver_webhook_notification(str(n.id))
        n.refresh_from_db()
        assert n.status == "sent"
        assert captured["headers"]["X-Nexus-Signature"].startswith("sha256=")

    def test_webhook_without_url_fails(self, ws, user):
        n = _notif(ws, user.id, channel="webhook")
        tasks.deliver_webhook_notification(str(n.id))
        n.refresh_from_db()
        assert n.status == "failed"

    def test_sms_not_configured_marks_failed(self, ws, user):
        n = _notif(ws, user.id, channel="sms")
        tasks.deliver_sms_notification(str(n.id))
        n.refresh_from_db()
        assert n.status == "failed"
        assert n.failed_reason == "sms_provider_not_configured"

    def test_retry_then_failed(self, ws, user, monkeypatch):
        def boom(notification):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(tasks, "_deliver_email", boom)
        n = _notif(ws, user.id, channel="email")
        with contextlib.suppress(Exception):
            tasks.deliver_email_notification(str(n.id))
        n.refresh_from_db()
        assert n.status == "failed"
        assert "smtp down" in n.failed_reason
