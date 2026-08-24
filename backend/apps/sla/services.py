"""
SLAService (PROJECT_HANDBOOK.md §28.2).

Attaches SLA timers to records (one ``SLARecord`` per policy × metric), supports
pause/resume (accumulating ``paused_seconds`` and shifting targets), and marks
metrics met. Breach/warning transitions are driven by the ``check_sla_breaches``
beat task. Policy applicability is decided by an in-memory NQL condition
(``applies_when_nql``) — the same evaluator the rules/workflow engines use.
"""
from __future__ import annotations

import uuid

from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.workflows import conditions

from .calculator import compute_target_at
from .models import SLAPolicy, SLARecord

_ACTIVE = ("on_track", "warning")


def _emit(sla_record, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=sla_record.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=sla_record.workspace_id,
        aggregate_type="sla_record", aggregate_id=sla_record.id, version=version,
        payload={"entity_id": str(sla_record.entity_id),
                 "record_id": str(sla_record.record_id),
                 "metric": sla_record.metric_key, **payload},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


class SLAService:
    @staticmethod
    def attach_policies(record_id, entity_slug, record_data, workspace_id,
                        entity_id=None) -> list[SLARecord]:
        policies = SLAPolicy.objects.filter(
            workspace_id=workspace_id, is_active=True, deleted_at__isnull=True)
        if entity_id is not None:
            policies = policies.filter(entity_id=entity_id)
        created = []
        now = timezone.now()
        for policy in policies:
            if policy.applies_when_nql and not conditions.evaluate(
                    policy.applies_when_nql, record_data or {}, workspace_id=workspace_id,
                    entity_slug=entity_slug):
                continue
            for target in (policy.targets or []):
                metric = target.get("metric")
                if not metric:
                    continue
                if SLARecord.objects.filter(
                        workspace_id=workspace_id, record_id=record_id,
                        policy_id=policy.id, metric_key=metric).exists():
                    continue
                target_at, warning_at = compute_target_at(policy, metric, now, workspace_id)
                rec = SLARecord.objects.create(
                    policy_id=policy.id, workspace_id=workspace_id,
                    entity_id=policy.entity_id, record_id=record_id, metric_key=metric,
                    status="on_track", started_at=now, target_at=target_at,
                    warning_at=warning_at)
                _emit(rec, "sla.started", {})
                created.append(rec)
        return created

    @staticmethod
    def pause_record(record_id, workspace_id) -> list[SLARecord]:
        now = timezone.now()
        records = list(SLARecord.objects.filter(
            workspace_id=workspace_id, record_id=record_id, status__in=_ACTIVE,
            paused_at__isnull=True))
        for rec in records:
            rec.paused_at = now
            rec.status = "paused"
            rec.save(update_fields=["paused_at", "status"])
        return records

    @staticmethod
    def resume_record(record_id, workspace_id) -> list[SLARecord]:
        import datetime as _dt
        now = timezone.now()
        records = list(SLARecord.objects.filter(
            workspace_id=workspace_id, record_id=record_id, status="paused",
            paused_at__isnull=False))
        for rec in records:
            delta = int((now - rec.paused_at).total_seconds())
            rec.paused_seconds += delta
            rec.target_at = rec.target_at + _dt.timedelta(seconds=delta)
            rec.warning_at = rec.warning_at + _dt.timedelta(seconds=delta)
            rec.paused_at = None
            rec.status = "on_track"
            rec.save(update_fields=["paused_seconds", "target_at", "warning_at",
                                    "paused_at", "status"])
        return records

    @staticmethod
    def mark_met(record_id, metric, workspace_id) -> SLARecord | None:
        rec = SLARecord.objects.filter(
            workspace_id=workspace_id, record_id=record_id, metric_key=metric).first()
        if rec is None or rec.status == "met":
            return rec
        rec.status = "met"
        rec.met_at = timezone.now()
        rec.save(update_fields=["status", "met_at"])
        _emit(rec, "sla.met", {})
        return rec

    @staticmethod
    def status_for(record_id, workspace_id):
        return list(SLARecord.objects.filter(
            workspace_id=workspace_id, record_id=record_id).order_by("metric_key"))

    @staticmethod
    def dashboard(workspace_id) -> dict:
        from django.db.models import Count
        qs = SLARecord.objects.filter(workspace_id=workspace_id)
        by_status = {row["status"]: row["n"] for row in
                     qs.values("status").annotate(n=Count("id"))}
        return {
            "breached": by_status.get("breached", 0),
            "warning": by_status.get("warning", 0),
            "on_track": by_status.get("on_track", 0),
            "met": by_status.get("met", 0),
            "paused": by_status.get("paused", 0),
        }
