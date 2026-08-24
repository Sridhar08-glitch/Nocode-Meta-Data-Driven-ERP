"""
ApprovalService (PROJECT_HANDBOOK.md §27.1).

Multi-level approval routing for a record. A request advances level-by-level;
each level passes by quorum (``any`` = first approve, ``all`` = every approver).
Any reject ends the request. On final approve/reject the process's
``on_*_actions`` run and, if the request was spawned by a workflow ``approval``
step, the workflow run is resumed (``resume_approval``).

Approver identities are **user ids** throughout (consistent with notifications +
the workflow actor); ``ApprovalDecision`` rows are the audit of each vote.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import ApprovalDecision, ApprovalProcess, ApprovalRequest


class ApprovalError(Exception):  # noqa: N818 — domain error
    pass


class ApprovalPermissionError(Exception):  # noqa: N818
    pass


def _emit(request, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=request.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=request.workspace_id,
        aggregate_type="approval_request", aggregate_id=request.id, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _level_config(process, level: int) -> dict:
    for lvl in (process.levels or []):
        if int(lvl.get("level", 0)) == level:
            return lvl
    return {}


def _max_level(process) -> int:
    return max((int(lvl.get("level", 0)) for lvl in (process.levels or [])), default=1)


def _record_field(workspace_id, entity_id, record_id, field_slug):
    """Read a single field off the record (for approver type=field)."""
    try:
        from apps.metadata.models import EntityDefinition
        from apps.records import dal
        entity = EntityDefinition.objects.filter(id=entity_id).first()
        if entity is None or not entity.table_name:
            return None
        fmap = dal.FieldMap(entity)
        row = dal.get_row(entity, fmap, record_id)
        return row.get(field_slug) if row else None
    except Exception:  # noqa: BLE001
        return None


def resolve_approvers(process, level: int, request) -> list[str]:
    """Resolve a level's approver specs to a list of user-id strings."""
    cfg = _level_config(process, level)
    out: list[str] = []
    for spec in cfg.get("approvers", []):
        kind = spec.get("type")
        value = spec.get("value")
        if kind == "member":
            out.append(str(value))
        elif kind == "role":
            from apps.tenancy.models import WorkspaceMember
            out.extend(str(uid) for uid in WorkspaceMember.objects.filter(
                workspace_id=request.workspace_id, role=value, status="active"
            ).values_list("user_id", flat=True))
        elif kind == "field":
            val = _record_field(request.workspace_id, request.entity_id,
                                request.record_id, value)
            if val:
                out.append(str(val))
    # de-dupe, preserve order
    seen, deduped = set(), []
    for uid in out:
        if uid not in seen:
            seen.add(uid)
            deduped.append(uid)
    return deduped


def _notify(request, approver_ids, level):
    try:
        from apps.notifications.services import NotificationService
    except Exception:  # noqa: BLE001
        return
    for uid in approver_ids:
        NotificationService.send(
            recipient_id=uid, recipient_type="member", template_slug="approval_requested",
            context={"event_type": "approval_requested", "subject": "Approval requested",
                     "body": f"An approval is awaiting your decision (level {level}).",
                     "record_id": str(request.record_id)},
            workspace_id=request.workspace_id, channels=["in_app"])


class ApprovalService:
    @staticmethod
    def create_request(*, process_id, record_id, entity_slug=None, requested_by,
                       workspace_id, workflow_run_id=None, step_run_id=None,
                       context=None) -> ApprovalRequest:
        process = ApprovalProcess.objects.filter(
            id=process_id, workspace_id=workspace_id).first()
        if process is None:
            raise ApprovalError("Approval process not found")
        level1 = _level_config(process, 1)
        expires_at = None
        if level1.get("timeout_hours"):
            expires_at = timezone.now() + timedelta(hours=int(level1["timeout_hours"]))
        request = ApprovalRequest.objects.create(
            workspace_id=workspace_id, process_id=process.id, entity_id=process.entity_id,
            record_id=record_id, status="pending", current_level=1,
            requested_by=requested_by, workflow_run_id=workflow_run_id,
            step_run_id=step_run_id, expires_at=expires_at)
        _notify(request, resolve_approvers(process, 1, request), 1)
        _emit(request, "approval.requested",
              {"process_id": str(process.id), "level": 1,
               "record_id": str(record_id), "entity_id": str(process.entity_id)},
              requested_by)
        return request

    @staticmethod
    def _load(request_id, workspace_id=None) -> ApprovalRequest:
        qs = ApprovalRequest.objects.filter(id=request_id)
        if workspace_id is not None:
            qs = qs.filter(workspace_id=workspace_id)
        req = qs.first()
        if req is None:
            raise ApprovalError("Approval request not found")
        return req

    @staticmethod
    def approve(request_id, approver_id, comment="", *, workspace_id=None) -> ApprovalRequest:
        request = ApprovalService._load(request_id, workspace_id)
        if request.status != "pending":
            raise ApprovalError(f"Request is not pending (status={request.status})")
        process = ApprovalProcess.objects.get(id=request.process_id)
        level = request.current_level
        approvers = resolve_approvers(process, level, request)
        if str(approver_id) not in approvers:
            raise ApprovalPermissionError("You are not an approver for this level")
        ApprovalDecision.objects.update_or_create(
            request_id=request.id, level=level, approver_id=approver_id,
            defaults={"workspace_id": request.workspace_id, "decision": "approve",
                      "comment": comment})
        cfg = _level_config(process, level)
        if not ApprovalService._quorum_met(request, level, cfg.get("quorum", "any"), approvers):
            return request  # waiting on more approvers at this level
        if level >= _max_level(process):
            return ApprovalService._finalize(request, process, "approved", approver_id, comment)
        # advance to the next level
        request.current_level = level + 1
        next_cfg = _level_config(process, request.current_level)
        if next_cfg.get("timeout_hours"):
            request.expires_at = timezone.now() + timedelta(hours=int(next_cfg["timeout_hours"]))
        request.save(update_fields=["current_level", "expires_at"])
        _notify(request, resolve_approvers(process, request.current_level, request),
                request.current_level)
        _emit(request, "approval.level_advanced",
              {"level": request.current_level}, approver_id)
        return request

    @staticmethod
    def reject(request_id, rejector_id, comment="", *, workspace_id=None) -> ApprovalRequest:
        request = ApprovalService._load(request_id, workspace_id)
        if request.status != "pending":
            raise ApprovalError(f"Request is not pending (status={request.status})")
        process = ApprovalProcess.objects.get(id=request.process_id)
        approvers = resolve_approvers(process, request.current_level, request)
        if str(rejector_id) not in approvers:
            raise ApprovalPermissionError("You are not an approver for this level")
        ApprovalDecision.objects.update_or_create(
            request_id=request.id, level=request.current_level, approver_id=rejector_id,
            defaults={"workspace_id": request.workspace_id, "decision": "reject",
                      "comment": comment})
        return ApprovalService._finalize(request, process, "rejected", rejector_id, comment)

    @staticmethod
    def cancel(request_id, actor_id, *, is_admin=False, workspace_id=None) -> ApprovalRequest:
        request = ApprovalService._load(request_id, workspace_id)
        if request.status != "pending":
            return request
        if str(request.requested_by) != str(actor_id) and not is_admin:
            raise ApprovalPermissionError("Only the requester or an admin can cancel")
        request.status = "cancelled"
        request.resolved_by = actor_id
        request.resolved_at = timezone.now()
        request.save(update_fields=["status", "resolved_by", "resolved_at"])
        _emit(request, "approval.cancelled", {}, actor_id)
        ApprovalService._resume_workflow(request, approved=False, comment="cancelled")
        return request

    @staticmethod
    def _quorum_met(request, level, quorum, approvers) -> bool:
        approvals = set(ApprovalDecision.objects.filter(
            request_id=request.id, level=level, decision="approve"
        ).values_list("approver_id", flat=True))
        approved_ids = {str(a) for a in approvals}
        if quorum == "all":
            return all(a in approved_ids for a in approvers) and len(approvers) > 0
        return len(approved_ids) >= 1  # "any"

    @staticmethod
    def _finalize(request, process, status, actor_id, comment) -> ApprovalRequest:
        request.status = status
        request.resolved_by = actor_id
        request.resolved_at = timezone.now()
        request.resolution_comment = comment or ""
        request.save(update_fields=["status", "resolved_by", "resolved_at",
                                    "resolution_comment"])
        actions = process.on_approve_actions if status == "approved" else process.on_reject_actions
        ApprovalService._execute_actions(actions or [], request)
        _emit(request, f"approval.{status}", {"comment": comment}, actor_id)
        ApprovalService._resume_workflow(request, approved=(status == "approved"),
                                         comment=comment)
        return request

    @staticmethod
    def _resume_workflow(request, *, approved, comment=""):
        if not request.workflow_run_id or not request.step_run_id:
            return
        try:
            from apps.workflows.services import WorkflowService
            WorkflowService.resume_approval(request.step_run_id, approved=approved,
                                            comment=comment)
        except Exception:  # noqa: BLE001 — workflow resume must not break approval resolution
            pass

    @staticmethod
    def _execute_actions(actions, request) -> None:
        for action in actions:
            atype = action.get("type")
            try:
                if atype == "trigger_workflow":
                    from apps.workflows.services import WorkflowService
                    WorkflowService.trigger_workflow(
                        workflow_id=action["workflow_id"], record_id=request.record_id,
                        workspace_id=request.workspace_id, trigger_type="manual")
                elif atype == "send_notification":
                    from apps.notifications.services import NotificationService
                    NotificationService.send(
                        recipient_id=action.get("recipient_id") or request.requested_by,
                        recipient_type="member", template_slug=action.get("template_slug", ""),
                        context={"event_type": "approval_action", "record_id": str(request.record_id),
                                 "subject": action.get("subject", "Approval update"),
                                 "body": action.get("body", "")},
                        workspace_id=request.workspace_id, channels=["in_app"])
                elif atype in ("update_field", "set_stage"):
                    ApprovalService._apply_record_update(request, action)
            except Exception:  # noqa: BLE001 — one bad action must not wedge resolution
                continue

    @staticmethod
    def _apply_record_update(request, action) -> None:
        from apps.records.services import RecordService, resolve_entity
        from apps.workflows.executors import SystemMember
        field = action.get("field") or ("stage" if action["type"] == "set_stage" else None)
        if not field:
            return
        try:
            entity = resolve_entity(request.workspace_id, action.get("entity_slug")) \
                if action.get("entity_slug") else _entity_for_request(request)
        except Exception:  # noqa: BLE001
            return
        if entity is None:
            return
        actor = request.resolved_by or request.requested_by or uuid.UUID(int=0)
        member = SystemMember(user_id=actor, id=actor)
        RecordService.update_record(workspace_id=request.workspace_id, member=member,
                                    entity=entity, record_id=request.record_id,
                                    data={field: action.get("value")})


    @staticmethod
    def pending_for(user_id, workspace_id):
        """Requests currently awaiting *user_id* at their current level."""
        pending = ApprovalRequest.objects.filter(
            workspace_id=workspace_id, status="pending")
        out = []
        for req in pending:
            process = ApprovalProcess.objects.filter(id=req.process_id).first()
            if process is None:
                continue
            if str(user_id) in resolve_approvers(process, req.current_level, req):
                out.append(req)
        return out


def _entity_for_request(request):
    from apps.metadata.models import EntityDefinition
    from apps.records.services import resolve_entity
    ent = EntityDefinition.objects.filter(id=request.entity_id).first()
    if ent is None:
        return None
    return resolve_entity(request.workspace_id, ent.slug)
