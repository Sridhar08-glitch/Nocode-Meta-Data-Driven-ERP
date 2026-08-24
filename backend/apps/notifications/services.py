"""
NotificationService (PROJECT_HANDBOOK.md §22.2).

``send`` renders a workspace template per channel, honours per-member preferences,
de-duplicates on an optional idempotency key, persists ``Notification`` rows
(``status="pending"``) and dispatches one Celery delivery task per channel.

A ``template_slug`` may map to several ``NotificationTemplate`` rows — one per
channel (``unique_together(workspace_id, slug, channel)``). When no template row
exists, ``send`` falls back to a literal subject/body taken from ``context`` so
callers (e.g. the workflow engine) never break.
"""
from __future__ import annotations

import uuid

from django.utils import timezone

from .models import Notification, NotificationPreference, NotificationTemplate
from .renderer import render_template, sanitize_html

_TASK_CHANNELS = {"in_app", "email", "webhook", "sms", "push"}


def _uuid_or_none(value):
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _pref_enabled(workspace_id, recipient_id, recipient_type, event_type, channel) -> bool:
    """Per-member channel preference for an event type (default enabled)."""
    if recipient_type != "member" or not event_type:
        return True
    pref = NotificationPreference.objects.filter(
        workspace_id=workspace_id, member_id=recipient_id,
        event_type=event_type, channel=channel).first()
    return pref.enabled if pref else True


def _dispatch(notification) -> None:
    from . import tasks
    fn = {
        "email": tasks.deliver_email_notification,
        "in_app": tasks.deliver_in_app_notification,
        "push": tasks.deliver_in_app_notification,
        "webhook": tasks.deliver_webhook_notification,
        "sms": tasks.deliver_sms_notification,
    }.get(notification.channel)
    if fn is not None:
        fn.delay(str(notification.id))


class NotificationService:
    @staticmethod
    def send(*, recipient_id, recipient_type="member", template_slug, context,
             workspace_id, channels=None) -> list[Notification]:
        context = dict(context or {})
        event_type = context.get("event_type", "")
        idem = context.get("idempotency_key")

        templates = list(NotificationTemplate.objects.filter(
            workspace_id=workspace_id, slug=template_slug)) if template_slug else []
        if channels:
            wanted = set(channels)
            templates = [t for t in templates if t.channel in wanted]

        pairs = [(t.channel, t) for t in templates]
        if not pairs:
            for ch in (channels or ["in_app"]):
                pairs.append((ch, None))

        created: list[Notification] = []
        for channel, template in pairs:
            if channel not in _TASK_CHANNELS:
                continue
            if not _pref_enabled(workspace_id, recipient_id, recipient_type,
                                 event_type, channel):
                continue
            if idem and Notification.objects.filter(
                    workspace_id=workspace_id, recipient_id=recipient_id,
                    channel=channel, idempotency_key=idem).exists():
                continue
            if template is not None:
                rendered = render_template(template, context)
            else:
                rendered = {
                    "subject": str(context.get("subject", "")),
                    "body": sanitize_html(str(context.get("body", ""))),
                    "short_body": "",
                }
            n = Notification.objects.create(
                workspace_id=workspace_id,
                template_id=getattr(template, "id", None),
                recipient_id=recipient_id, recipient_type=recipient_type,
                channel=channel, status="pending",
                subject=rendered["subject"][:500], body=rendered["body"],
                action_url=str(context.get("action_url", ""))[:2000],
                entity_id=_uuid_or_none(context.get("entity_id")),
                record_id=_uuid_or_none(context.get("record_id")),
                group_key=str(context.get("group_key", ""))[:255],
                actor_id=_uuid_or_none(context.get("actor_id")),
                idempotency_key=idem or "")
            _dispatch(n)
            created.append(n)
        return created

    @staticmethod
    def mark_read(notification_id, user_id) -> Notification | None:
        n = Notification.objects.filter(id=notification_id, recipient_id=user_id).first()
        if n is None:
            return None
        if n.read_at is None:
            n.read_at = timezone.now()
            n.status = "read"
            n.save(update_fields=["read_at", "status"])
        return n

    @staticmethod
    def mark_all_read(user_id, workspace_id) -> int:
        return Notification.objects.filter(
            workspace_id=workspace_id, recipient_id=user_id, read_at__isnull=True
        ).update(read_at=timezone.now(), status="read")

    @staticmethod
    def get_unread_count(user_id, workspace_id) -> int:
        return Notification.objects.filter(
            workspace_id=workspace_id, recipient_id=user_id, read_at__isnull=True
        ).count()
