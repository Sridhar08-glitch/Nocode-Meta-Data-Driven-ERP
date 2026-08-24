"""
SLA Celery task (PROJECT_HANDBOOK.md §28.3).

``check_sla_breaches`` (beat, every 5 min) advances active, non-paused SLA records
to ``warning`` then ``breached`` as their thresholds pass, emitting events,
notifying configured recipients, and firing ``sla_breached`` workflows.
"""
from __future__ import annotations

from django.utils import timezone

from celery import shared_task

from .models import SLAPolicy, SLARecord
from .services import _emit

_ACTIVE = ("on_track", "warning")


def _notify(policy, sla_record, kind):
    try:
        from apps.notifications.services import NotificationService
    except Exception:  # noqa: BLE001
        return
    recipients = []
    for action in (policy.escalation_actions or []):
        if action.get("type") == "notify" and action.get("recipient_id"):
            recipients.append(action["recipient_id"])
    for rid in recipients:
        NotificationService.send(
            recipient_id=rid, recipient_type="member",
            template_slug=f"sla_{kind}",
            context={"event_type": f"sla_{kind}", "subject": f"SLA {kind}",
                     "body": f"SLA {kind} for metric {sla_record.metric_key}.",
                     "record_id": str(sla_record.record_id)},
            workspace_id=sla_record.workspace_id, channels=["in_app"])


def _dispatch_breach_workflows(policy, sla_record):
    try:
        from apps.metadata.models import EntityDefinition
        from apps.workflows.dispatcher import run_record_event
        entity = EntityDefinition.objects.filter(id=sla_record.entity_id).first()
        slug = entity.slug if entity else ""
        run_record_event(
            event_type="sla_breached", entity_slug=slug, entity_id=sla_record.entity_id,
            record_id=sla_record.record_id,
            record={"entity_slug": slug, "metric": sla_record.metric_key},
            workspace_id=sla_record.workspace_id)
    except Exception:  # noqa: BLE001 — workflow dispatch must not wedge the beat
        pass


@shared_task(name="sla.check_sla_breaches")
def check_sla_breaches() -> dict:
    now = timezone.now()
    counts = {"warning": 0, "breached": 0}
    records = SLARecord.objects.filter(status__in=_ACTIVE, paused_at__isnull=True)
    policies: dict = {}
    for rec in records.iterator(chunk_size=200):
        policy = policies.get(rec.policy_id)
        if policy is None:
            policy = SLAPolicy.objects.filter(id=rec.policy_id).first()
            policies[rec.policy_id] = policy
        if now >= rec.target_at:
            rec.status = "breached"
            rec.breached_at = now
            rec.breach_notified = True
            rec.save(update_fields=["status", "breached_at", "breach_notified"])
            _emit(rec, "sla.breached", {})
            if policy:
                _notify(policy, rec, "breached")
                _dispatch_breach_workflows(policy, rec)
            counts["breached"] += 1
        elif now >= rec.warning_at and not rec.warning_sent:
            rec.status = "warning"
            rec.warning_sent = True
            rec.save(update_fields=["status", "warning_sent"])
            _emit(rec, "sla.warning", {})
            if policy:
                _notify(policy, rec, "warning")
            counts["warning"] += 1
    return counts
