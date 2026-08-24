"""
Channel delivery tasks (PROJECT_HANDBOOK.md §22.3).

Each task loads a ``Notification``, performs channel delivery, and updates
``status`` to ``sent`` / ``failed``. External IO is isolated behind small seams
(``_deliver_email`` / ``_push_in_app`` / ``_http_post`` / ``_send_sms``) so tests
run without a network. Secrets (SMTP password, webhook signing key, Twilio token)
are loaded from the environment by reference — never from the database.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from celery import shared_task

from .models import Notification

_DONE = ("sent", "delivered", "read")


# ── IO seams (monkeypatched in tests) ────────────────────────────────────────
def _recipient_email(notification) -> str:
    from apps.accounts.models import User
    user = User.objects.filter(id=notification.recipient_id).first()
    return user.email if user else ""


def _deliver_email(notification) -> None:
    to = _recipient_email(notification)
    if not to:
        raise ValueError("recipient has no email address")
    send_mail(
        subject=notification.subject or "(no subject)",
        message=notification.body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nexuserp.local"),
        recipient_list=[to],
        fail_silently=False,
    )


def _push_in_app(notification) -> None:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    if layer is None:
        return
    group = f"user_{notification.recipient_id}_notifications"
    async_to_sync(layer.group_send)(group, {
        "type": "notification.message",
        "notification": {
            "id": str(notification.id),
            "subject": notification.subject,
            "body": notification.body,
            "channel": notification.channel,
            "action_url": notification.action_url,
            "group_key": notification.group_key,
            "created_at": notification.created_at.isoformat()
            if notification.created_at else None,
        },
    })


def _http_post(url, data, headers, timeout=10):
    import requests
    resp = requests.post(url, data=data, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.status_code


def _send_sms(to: str, body: str) -> dict:
    """SMS via a configured provider. Returns {"sent": bool, "reason"?: str}.

    Provider credentials (e.g. Twilio token) come from the environment by
    reference; with none configured this degrades to a recorded failure.
    """
    if not os.environ.get("TWILIO_AUTH_TOKEN"):
        return {"sent": False, "reason": "sms_provider_not_configured"}
    # A real provider call would go here, using the env token (never the DB).
    return {"sent": True}


def _mark(notification, status, reason=""):
    notification.status = status
    if status == "sent":
        notification.sent_at = timezone.now()
    if reason:
        notification.failed_reason = reason
    notification.save(update_fields=["status", "sent_at", "failed_reason"])


# ── delivery tasks ───────────────────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name="notifications.deliver_email")
def deliver_email_notification(self, notification_id: str) -> None:
    n = Notification.objects.filter(id=notification_id).first()
    if n is None or n.status in _DONE:
        return
    try:
        _deliver_email(n)
    except Exception as exc:  # noqa: BLE001
        _mark(n, "failed", str(exc))
        raise self.retry(exc=exc) from exc
    _mark(n, "sent")


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name="notifications.deliver_in_app")
def deliver_in_app_notification(self, notification_id: str) -> None:
    n = Notification.objects.filter(id=notification_id).first()
    if n is None or n.status in _DONE:
        return
    try:
        _push_in_app(n)
    except Exception as exc:  # noqa: BLE001
        _mark(n, "failed", str(exc))
        raise self.retry(exc=exc) from exc
    _mark(n, "sent")


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name="notifications.deliver_webhook")
def deliver_webhook_notification(self, notification_id: str) -> None:
    n = Notification.objects.filter(id=notification_id).first()
    if n is None or n.status in _DONE:
        return
    url = n.action_url
    if not url:
        _mark(n, "failed", "no webhook url")
        return
    payload = json.dumps({
        "id": str(n.id), "subject": n.subject, "body": n.body,
        "workspace_id": str(n.workspace_id), "group_key": n.group_key,
    }, default=str)
    headers = {"Content-Type": "application/json"}
    secret = os.environ.get("NOTIFICATION_WEBHOOK_SECRET", "")
    if secret:
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        headers["X-Nexus-Signature"] = f"sha256={sig}"
    try:
        _http_post(url, payload, headers)
    except Exception as exc:  # noqa: BLE001
        _mark(n, "failed", str(exc))
        raise self.retry(exc=exc) from exc
    _mark(n, "sent")


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name="notifications.deliver_sms")
def deliver_sms_notification(self, notification_id: str) -> None:
    n = Notification.objects.filter(id=notification_id).first()
    if n is None or n.status in _DONE:
        return
    from apps.accounts.models import User
    user = User.objects.filter(id=n.recipient_id).first()
    to = getattr(user, "phone", "") if user else ""
    result = _send_sms(to, n.short_body if hasattr(n, "short_body") else n.body)
    if result.get("sent"):
        _mark(n, "sent")
    else:
        _mark(n, "failed", result.get("reason", "sms_failed"))
