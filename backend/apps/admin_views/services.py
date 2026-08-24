"""
Tenant-health metrics (Phase 1.31).

Operational metrics for the admin Health dashboard, sourced from data the platform
already records (workflow runs, the event store, physical-table stats) — no new
collectors. Everything is workspace-scoped. Per the hard constraints there is **no AI
metric**. Metrics we don't yet collect (HTTP/queue latency, plan limits) are returned as
``null`` rather than faked, so the UI can show "not collected" instead of a wrong number.
"""
from __future__ import annotations

import math
import uuid
from datetime import timedelta

from django.utils import timezone

_SYSTEM_ACTOR = uuid.UUID(int=0)


def _percentile(values: list[int], pct: float):
    if not values:
        return None
    ordered = sorted(values)
    k = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[min(k, len(ordered) - 1)]


def _distinct_actors(workspace_id, since) -> int:
    from apps.eventstore.models import DomainEvent
    ids = (DomainEvent.objects
           .filter(workspace_id=workspace_id, occurred_at__gte=since)
           .exclude(actor_id=_SYSTEM_ACTOR)
           .exclude(actor_id__isnull=True)
           .values_list("actor_id", flat=True).distinct())
    return len(set(ids))


def compute_health(workspace_id) -> dict:
    from apps.eventstore.models import DomainEvent
    from apps.metadata.models import EntityDefinition, EntityPhysicalTable
    from apps.workflows.models import WorkflowRun

    now = timezone.now()
    d1, d7, d30 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)

    runs = WorkflowRun.objects.filter(workspace_id=workspace_id)
    by_status = {s: runs.filter(status=s).count()
                 for s in ("completed", "failed", "running", "queued")}
    total_runs = runs.count()
    finished = by_status["completed"] + by_status["failed"]
    success_rate = round(by_status["completed"] / finished, 4) if finished else None

    runs_24h = runs.filter(created_at__gte=d1).count()
    failures_24h = runs.filter(created_at__gte=d1, status="failed").count()
    error_rate_24h = round(failures_24h / runs_24h, 4) if runs_24h else None

    durations = list(runs.filter(duration_ms__isnull=False)
                     .values_list("duration_ms", flat=True))

    rec_events = DomainEvent.objects.filter(
        workspace_id=workspace_id, aggregate_type="record", event_type="record.created")

    entity_count = EntityDefinition.objects.filter(
        workspace_id=workspace_id, is_active=True).count()
    row_estimate = sum(EntityPhysicalTable.objects.filter(workspace_id=workspace_id)
                       .values_list("row_count", flat=True))

    return {
        "workspace_id": str(workspace_id),
        "generated_at": now.isoformat(),
        "workflows": {
            "total": total_runs,
            "completed": by_status["completed"],
            "failed": by_status["failed"],
            "running": by_status["running"],
            "queued": by_status["queued"],
            "success_rate": success_rate,
        },
        "workflow_latency_ms": {
            "p50": _percentile(durations, 50),
            "p95": _percentile(durations, 95),
            "p99": _percentile(durations, 99),
            "count": len(durations),
        },
        "activity": {
            "dau": _distinct_actors(workspace_id, d1),
            "wau": _distinct_actors(workspace_id, d7),
            "mau": _distinct_actors(workspace_id, d30),
        },
        "records": {
            "created_24h": rec_events.filter(occurred_at__gte=d1).count(),
            "created_7d": rec_events.filter(occurred_at__gte=d7).count(),
            "created_total": rec_events.count(),
        },
        "errors": {
            "workflow_runs_24h": runs_24h,
            "workflow_failures_24h": failures_24h,
            "error_rate_24h": error_rate_24h,
        },
        "storage": {
            "entity_count": entity_count,
            "row_count_estimate": row_estimate,
        },
        # Not yet instrumented — returned as null so the UI shows "not collected".
        "api_latency_ms": None,
        "queue": None,
        "plan_limits": None,
        # Hard constraint: Sridhar ERP has no AI features → no AI metric, by design.
        "ai": None,
    }
