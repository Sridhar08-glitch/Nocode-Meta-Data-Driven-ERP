"""
Dependency health checks for the operational readiness probe (Phase P1.6).

Each check is isolated, time-bounded, and never raises — it returns a small dict
``{"ok": bool, "detail": str}`` so a single failing dependency degrades the readiness
report rather than 500-ing the probe itself. These power ``GET /readyz/`` (load-balancer /
orchestrator readiness gate) and are deliberately unauthenticated + workspace-agnostic.
"""
from __future__ import annotations

import time

from django.core.cache import cache
from django.db import connection


def _timed(fn):
    start = time.monotonic()
    try:
        fn()
        return {"ok": True, "detail": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 — a probe must report, never propagate
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.monotonic() - start) * 1000, 1)}


def check_database() -> dict:
    """A trivial round-trip confirms the primary DB connection is alive."""
    def _q():
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    return _timed(_q)


def check_cache() -> dict:
    """Write+read a sentinel key through the configured cache (Redis in prod)."""
    def _c():
        key = "_ops_readiness_probe"
        cache.set(key, "1", timeout=5)
        if cache.get(key) != "1":
            raise RuntimeError("cache set/get mismatch")
    return _timed(_c)


def check_broker() -> dict:
    """
    Confirm the Celery broker is reachable by opening (and immediately releasing) a
    connection with a short timeout. Lazy-imported so importing this module never drags
    in Celery during unrelated tooling.
    """
    def _b():
        from config.celery import app as celery_app

        conn = celery_app.connection(connect_timeout=2)
        try:
            conn.ensure_connection(max_retries=1, timeout=2)
        finally:
            conn.release()
    return _timed(_b)


def run_readiness_checks() -> tuple[bool, dict]:
    """
    Run every dependency check. Returns ``(all_ok, components)``. Cache/broker failures
    in local/dev (no Redis running) correctly surface as not-ready without crashing.
    """
    components = {
        "database": check_database(),
        "cache": check_cache(),
        "broker": check_broker(),
    }
    all_ok = all(c["ok"] for c in components.values())
    return all_ok, components
