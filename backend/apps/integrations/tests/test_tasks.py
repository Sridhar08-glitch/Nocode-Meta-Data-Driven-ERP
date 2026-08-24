"""Webhook delivery + retry (PROJECT_HANDBOOK.md §30.2 / §30.5)."""
import pytest

from apps.integrations import tasks
from apps.integrations.models import WebhookDelivery, WebhookSubscription
from apps.integrations.tasks import _backoff_seconds, deliver_webhook, retry_failed_deliveries


def _ok(*a, **k):
    return {"status": 200, "body": {"ok": True}, "headers": {}}


def _fail(*a, **k):
    return {"status": 500, "body": "err", "headers": {}}


def test_backoff_doubles():
    assert [_backoff_seconds(i) for i in range(1, 6)] == [30, 60, 120, 240, 480]


@pytest.mark.django_db
class TestDeliver:
    def test_success_signs_and_logs(self, ws, subscription, monkeypatch):
        captured = {}
        monkeypatch.setenv("WH", "secret")

        def fake(method, url, *, headers=None, data=None, timeout=10, **k):
            captured.update(headers=headers, data=data)
            return _ok()

        monkeypatch.setattr(tasks, "_http_request", fake)
        sub = subscription(signing_secret_ref="WH")
        assert deliver_webhook(str(sub.id), "record.created", {"id": 1}) == "success"
        d = WebhookDelivery.objects.get(subscription_id=sub.id)
        assert d.status == "success"
        assert d.request_body_hash and d.request_body_hash != captured["data"]  # hash, not raw
        assert captured["headers"]["X-Nexus-Signature"].startswith("sha256=")
        sub.refresh_from_db()
        assert sub.success_count == 1 and sub.consecutive_failures == 0

    def test_failure_schedules_retry(self, ws, subscription, monkeypatch):
        monkeypatch.setattr(tasks, "_http_request", _fail)
        sub = subscription(max_retries=3)
        deliver_webhook(str(sub.id), "e", {})
        d = WebhookDelivery.objects.get(subscription_id=sub.id)
        assert d.status == "retrying"
        assert d.next_retry_at is not None
        sub.refresh_from_db()
        assert sub.consecutive_failures == 1

    def test_disables_after_ten_failures(self, ws, subscription, monkeypatch):
        monkeypatch.setattr(tasks, "_http_request", _fail)
        sub = subscription(max_retries=3)
        WebhookSubscription.objects.filter(id=sub.id).update(consecutive_failures=9)
        deliver_webhook(str(sub.id), "e", {})
        sub.refresh_from_db()
        assert sub.status == "disabled_too_many_errors"

    def test_retry_failed_redispatches(self, ws, subscription, monkeypatch):
        calls = {"n": 0}

        def fake(*a, **k):
            calls["n"] += 1
            return _fail()

        monkeypatch.setattr(tasks, "_http_request", fake)
        sub = subscription(max_retries=3)
        deliver_webhook(str(sub.id), "e", {})           # attempt 1 → retrying
        from django.utils import timezone
        WebhookDelivery.objects.filter(subscription_id=sub.id).update(
            next_retry_at=timezone.now())
        retry_failed_deliveries()                        # → attempt 2
        assert calls["n"] == 2
