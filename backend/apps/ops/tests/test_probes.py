"""Tests for the operational liveness/readiness probes (Phase P1.6)."""
import pytest
from rest_framework.test import APIClient

from apps.ops import checks


@pytest.fixture
def client():
    return APIClient()


class TestLiveness:
    def test_liveness_is_200_and_unauthenticated(self, client):
        resp = client.get("/healthz/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
class TestReadiness:
    def test_database_check_ok(self):
        result = checks.check_database()
        assert result["ok"] is True
        assert "latency_ms" in result

    def test_check_reports_failure_without_raising(self, monkeypatch):
        # A broken dependency must degrade the report, never propagate.
        def boom():
            raise RuntimeError("redis down")

        monkeypatch.setattr(checks.cache, "set", lambda *a, **k: boom())
        result = checks.check_cache()
        assert result["ok"] is False
        assert "redis down" in result["detail"]

    def test_readiness_503_when_a_component_is_down(self, client, monkeypatch):
        monkeypatch.setattr(checks, "check_broker", lambda: {"ok": False, "detail": "no broker", "latency_ms": 0.0})
        monkeypatch.setattr(checks, "check_cache", lambda: {"ok": True, "detail": "ok", "latency_ms": 0.0})
        resp = client.get("/readyz/")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["broker"]["ok"] is False
        assert body["checks"]["database"]["ok"] is True

    def test_readiness_200_when_all_components_up(self, client, monkeypatch):
        ok = {"ok": True, "detail": "ok", "latency_ms": 0.0}
        monkeypatch.setattr(checks, "check_database", lambda: ok)
        monkeypatch.setattr(checks, "check_cache", lambda: ok)
        monkeypatch.setattr(checks, "check_broker", lambda: ok)
        resp = client.get("/readyz/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


class TestRequestId:
    def test_response_echoes_a_generated_request_id(self, client):
        resp = client.get("/healthz/")
        assert resp.headers["X-Request-ID"]

    def test_inbound_request_id_is_preserved(self, client):
        resp = client.get("/healthz/", HTTP_X_REQUEST_ID="trace-abc-123")
        assert resp.headers["X-Request-ID"] == "trace-abc-123"
