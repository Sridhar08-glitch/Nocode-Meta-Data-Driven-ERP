"""Integrations REST API + inbound endpoint (PROJECT_HANDBOOK.md §30.4 / §30.5)."""
import pytest
from rest_framework.test import APIClient

from apps.eventstore.models import DomainEvent
from apps.integrations.models import InboundWebhook

from .conftest import make_client

BASE = "/api/v1/integrations"


@pytest.mark.django_db
class TestSubscriptionApi:
    def test_crud_and_toggle(self, client):
        r = client.post(f"{BASE}/webhooks/subscriptions/",
                        {"name": "S", "target_url": "https://h.example/x",
                         "event_types": ["record.created"]}, format="json")
        assert r.status_code == 201, r.content
        sid = r.json()["id"]
        assert client.get(f"{BASE}/webhooks/subscriptions/").json()["count"] == 1
        assert client.post(f"{BASE}/webhooks/subscriptions/{sid}/disable/").json()["status"] == "paused"
        assert client.post(f"{BASE}/webhooks/subscriptions/{sid}/enable/").json()["status"] == "active"

    def test_test_delivery(self, client, monkeypatch):
        from apps.integrations import tasks
        monkeypatch.setattr(tasks, "_http_request",
                            lambda *a, **k: {"status": 200, "body": {}, "headers": {}})
        sid = client.post(f"{BASE}/webhooks/subscriptions/",
                          {"name": "S", "target_url": "https://h.example/x"},
                          format="json").json()["id"]
        r = client.post(f"{BASE}/webhooks/subscriptions/{sid}/test/")
        assert r.status_code == 200 and r.json()["delivered"] is True
        assert client.get(f"{BASE}/webhooks/subscriptions/{sid}/deliveries/").json()["count"] == 1


@pytest.mark.django_db
class TestConnectorApi:
    def test_crud_and_test(self, client, monkeypatch):
        from apps.integrations import services
        monkeypatch.setattr(services, "_http_request",
                            lambda *a, **k: {"status": 204, "body": "", "headers": {}})
        r = client.post(f"{BASE}/connectors/",
                        {"name": "C", "slug": "c", "base_url": "https://api.example",
                         "auth_type": "none"}, format="json")
        assert r.status_code == 201
        cid = r.json()["id"]
        assert client.post(f"{BASE}/connectors/{cid}/test/",
                           {"method": "GET", "path": "/ping"}, format="json").json()["status"] == 204


@pytest.mark.django_db
class TestInboundApi:
    def test_create_returns_token_once_and_rotate(self, client):
        r = client.post(f"{BASE}/inbound-webhooks/", {"name": "I", "slug": "i"}, format="json")
        assert r.status_code == 201
        token = r.json()["token"]
        assert token
        iid = r.json()["id"]
        # detail must NOT expose the token
        assert "token" not in client.get(f"{BASE}/inbound-webhooks/{iid}/").json()
        old_hash = InboundWebhook.objects.get(id=iid).token_hash
        new_token = client.post(f"{BASE}/inbound-webhooks/{iid}/rotate-token/").json()["token"]
        assert new_token != token
        assert InboundWebhook.objects.get(id=iid).token_hash != old_hash


@pytest.mark.django_db
class TestInboundReceive:
    def test_valid_token_dispatches_and_hides_body(self, client, ws):
        token = client.post(f"{BASE}/inbound-webhooks/", {"name": "I", "slug": "i"},
                            format="json").json()["token"]
        anon = APIClient()
        r = anon.post(f"/api/v1/webhooks/inbound/{token}/", {"hello": "world"}, format="json")
        assert r.status_code == 200 and r.json()["received"] is True
        ev = DomainEvent.objects.filter(event_type="inbound_webhook.received").first()
        assert ev is not None
        assert "body_hash" in ev.payload
        assert "hello" not in str(ev.payload)   # raw body never stored

    def test_invalid_token_404(self):
        assert APIClient().post("/api/v1/webhooks/inbound/bogus/", {}, format="json").status_code == 404


@pytest.mark.django_db
class TestAuthz:
    def test_viewer_cannot_create_subscription(self, ws):
        _, c = make_client(ws, "v@acme.com", role="viewer")
        r = c.post(f"{BASE}/webhooks/subscriptions/",
                   {"name": "S", "target_url": "https://h.example/x"}, format="json")
        assert r.status_code == 403
