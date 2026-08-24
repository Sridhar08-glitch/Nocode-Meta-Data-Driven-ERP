"""
Webhook delivery tasks (PROJECT_HANDBOOK.md §30.2).

``deliver_webhook`` performs one signed POST and records a ``WebhookDelivery``
(storing only a SHA-256 of the body, never the raw payload). Failures schedule a
retry with exponential backoff (30, 60, 120, 240, 480s); ``retry_failed_deliveries``
re-dispatches due deliveries. A subscription auto-disables after 10 consecutive
failures.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.utils import timezone

from celery import shared_task

from .models import WebhookDelivery, WebhookSubscription
from .services import WebhookService, _http_request

_BACKOFF = [30, 60, 120, 240, 480]
_MAX_CONSECUTIVE = 10


def _backoff_seconds(attempt: int) -> int:
    return _BACKOFF[min(attempt, len(_BACKOFF)) - 1]


@shared_task(name="integrations.deliver_webhook")
def deliver_webhook(subscription_id: str, event_type: str, payload: dict,
                    event_id: str = None, attempt: int = 1) -> str:
    sub = WebhookSubscription.objects.filter(id=subscription_id).first()
    if sub is None or sub.status != "active":
        return "skipped"
    body, headers = WebhookService.build_payload(event_type, payload, sub)
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    started = timezone.now()
    result, error = None, ""
    try:
        result = _http_request(sub.http_method, sub.target_url, headers=headers,
                               data=body, timeout=sub.timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    duration = int((timezone.now() - started).total_seconds() * 1000)
    status_code = result["status"] if result else None
    ok = bool(status_code and 200 <= status_code < 300)

    delivery = WebhookDelivery.objects.create(
        subscription_id=sub.id, workspace_id=sub.workspace_id,
        event_id=event_id or sub.id, event_type=event_type,
        status="success" if ok else "failed", attempt_number=attempt,
        request_headers={k: v for k, v in headers.items() if k != "Authorization"},
        request_body_hash=body_hash, response_status=status_code,
        response_body_snippet=str(result["body"])[:500] if result else "",
        duration_ms=duration, error_message=error)

    if ok:
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["delivered_at"])
        WebhookSubscription.objects.filter(id=sub.id).update(
            success_count=sub.success_count + 1, consecutive_failures=0,
            last_fired_at=timezone.now())
        return "success"

    consecutive = sub.consecutive_failures + 1
    updates = {"failure_count": sub.failure_count + 1,
               "consecutive_failures": consecutive, "last_error_at": timezone.now()}
    if consecutive >= _MAX_CONSECUTIVE:
        updates["status"] = "disabled_too_many_errors"
    elif attempt < sub.max_retries:
        delivery.status = "retrying"
        delivery.next_retry_at = timezone.now() + timedelta(seconds=_backoff_seconds(attempt))
        delivery.save(update_fields=["status", "next_retry_at"])
    WebhookSubscription.objects.filter(id=sub.id).update(**updates)
    return "failed"


@shared_task(name="integrations.retry_failed_deliveries")
def retry_failed_deliveries() -> int:
    now = timezone.now()
    due = WebhookDelivery.objects.filter(
        status="retrying", next_retry_at__lte=now).order_by("next_retry_at")[:500]
    count = 0
    for delivery in due:
        sub = WebhookSubscription.objects.filter(id=delivery.subscription_id).first()
        if sub is None or sub.status != "active" or delivery.attempt_number >= sub.max_retries:
            delivery.status = "failed"
            delivery.save(update_fields=["status"])
            continue
        delivery.status = "failed"   # superseded by the new attempt row
        delivery.save(update_fields=["status"])
        deliver_webhook.delay(str(sub.id), delivery.event_type, {},
                              str(delivery.event_id), delivery.attempt_number + 1)
        count += 1
    return count
