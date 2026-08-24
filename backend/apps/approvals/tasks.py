"""
Approval timeout task (PROJECT_HANDBOOK.md §27.2).

Celery beat (every 15 min) resolves pending requests past their ``expires_at``
per the level's ``on_timeout`` policy: ``auto_approve`` / ``auto_reject`` /
``escalate`` (advance to the next level, re-notify).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from celery import shared_task

from .models import ApprovalProcess, ApprovalRequest
from .services import ApprovalService, _level_config, _max_level, _notify, resolve_approvers


@shared_task(name="approvals.check_approval_timeout")
def check_approval_timeout() -> dict:
    now = timezone.now()
    due = ApprovalRequest.objects.filter(
        status="pending", expires_at__isnull=False, expires_at__lt=now)
    counts = {"auto_approved": 0, "auto_rejected": 0, "escalated": 0}
    for request in due:
        process = ApprovalProcess.objects.filter(id=request.process_id).first()
        if process is None:
            continue
        cfg = _level_config(process, request.current_level)
        policy = cfg.get("on_timeout", "auto_reject")
        if policy == "auto_approve":
            approvers = resolve_approvers(process, request.current_level, request)
            actor = approvers[0] if approvers else request.requested_by
            ApprovalService._finalize(request, process, "approved", actor, "timeout: auto-approved")
            counts["auto_approved"] += 1
        elif policy == "escalate" and request.current_level < _max_level(process):
            request.current_level += 1
            next_cfg = _level_config(process, request.current_level)
            request.expires_at = (
                now + timedelta(hours=int(next_cfg["timeout_hours"]))
                if next_cfg.get("timeout_hours") else None)
            request.save(update_fields=["current_level", "expires_at"])
            _notify(request, resolve_approvers(process, request.current_level, request),
                    request.current_level)
            counts["escalated"] += 1
        else:  # auto_reject (default) or escalate at final level
            ApprovalService._finalize(request, process, "rejected", request.requested_by,
                                      "timeout: auto-rejected")
            counts["auto_rejected"] += 1
        from apps.approvals.services import _emit
        _emit(request, "approval.timed_out", {"policy": policy}, None)
    return counts
