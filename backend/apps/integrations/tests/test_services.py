"""WebhookService + HTTPConnectorService (PROJECT_HANDBOOK.md §30.1 / §30.5)."""
import hashlib
import hmac
import json

import pytest

from apps.integrations import services
from apps.integrations.services import HTTPConnectorService, WebhookService


@pytest.mark.django_db
class TestBuildPayload:
    def test_signs_with_secret(self, ws, subscription, monkeypatch):
        monkeypatch.setenv("WH_SECRET", "s3cr3t")
        sub = subscription(signing_secret_ref="WH_SECRET")
        body, headers = WebhookService.build_payload("record.created", {"id": 1}, sub)
        expected = hmac.new(b"s3cr3t", body.encode(), hashlib.sha256).hexdigest()
        assert headers["X-Nexus-Signature"] == f"sha256={expected}"
        assert json.loads(body)["event"] == "record.created"

    def test_no_signature_without_secret(self, ws, subscription):
        sub = subscription()
        _body, headers = WebhookService.build_payload("e", {}, sub)
        assert "X-Nexus-Signature" not in headers


@pytest.mark.django_db
class TestConnector:
    def test_bearer_auth_applied(self, ws, connector, monkeypatch):
        captured = {}

        def fake(method, url, *, headers=None, params=None, data=None, timeout=10):
            captured.update(method=method, url=url, headers=headers)
            return {"status": 200, "body": {}, "headers": {}}

        monkeypatch.setattr(services, "_http_request", fake)
        monkeypatch.setenv("TOK", "abc123")
        conn = connector(auth_type="bearer_token", auth_config={"token_ref": "TOK"})
        HTTPConnectorService.request(conn, "GET", "/ping")
        assert captured["headers"]["Authorization"] == "Bearer abc123"
        assert captured["url"] == "https://api.example/ping"

    def test_api_key_header(self, ws, connector, monkeypatch):
        captured = {}
        monkeypatch.setattr(services, "_http_request",
                            lambda *a, **k: captured.update(k) or {"status": 200, "body": {}})
        monkeypatch.setenv("KEY", "xyz")
        conn = connector(auth_type="api_key_header",
                         auth_config={"header_name": "X-Key", "key_ref": "KEY"})
        HTTPConnectorService.request(conn, "GET", "ping")
        assert captured["headers"]["X-Key"] == "xyz"
