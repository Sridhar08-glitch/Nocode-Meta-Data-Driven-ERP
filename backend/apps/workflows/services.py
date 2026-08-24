"""
WorkflowService — the workflow execution engine (PROJECT_HANDBOOK.md §21.1).

Lifecycle:  ``trigger_workflow`` → entry steps → ``execute_workflow_step`` (Celery)
→ ``complete_step`` / ``fail_step`` → graph traversal along ``WorkflowEdge`` →
run reaches ``completed`` / ``failed`` / ``cancelled``.

Graph execution notes:
  * Any step that emits a ``{"branch": ...}`` output picks edges by ``condition_label`` matching
    that branch — ``condition`` AND the Guard Framework's ``action_guard`` (Gap A) both do; steps
    that emit no branch follow every outgoing edge whose ``condition_expr`` (NQL, in-memory) passes.
  * ``parallel`` fans out (default multi-edge behaviour); ``join`` waits until all
    of its incoming branches have arrived (arrival counter on the run context).
  * Successor step-runs are created (``pending``) *before* any is enqueued so that
    under eager Celery a fast branch cannot mark the run complete while a sibling
    branch is still pending.

All writes are workspace-scoped; record actions go through ``RecordService`` so
RBAC/ABAC + PostgreSQL RLS are enforced at the DAL.
"""
from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import conditions
from .events import emit_workflow_event
from .executors import HALT_KEY, get_executor, member_for_run
from .models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepRun,
)

_ACTIVE_STEP_STATES = ("pending", "running", "waiting_approval")
_CONTROL_KEYS = {"branch", "matched", "joined", HALT_KEY, "status"}


class WorkflowError(Exception):
    """Base error for the workflow engine."""


class WorkflowConcurrencyError(WorkflowError):
    """Raised when a definition's ``max_concurrent_runs`` ceiling is reached."""


def _now():
    return timezone.now()


def _ms(start, end) -> int | None:
    if not start or not end:
        return None
    return int((end - start).total_seconds() * 1000)


def _record_view(run, ctx) -> dict:
    """Flat record dict for in-memory condition evaluation."""
    rec = dict(ctx.get("record") or {})
    for k, v in (ctx or {}).items():
        if not isinstance(v, (dict | list)):
            rec.setdefault(k, v)
    return rec


class WorkflowService:
    # ── trigger / run creation ────────────────────────────────────────────────
    @staticmethod
    def trigger_workflow(*, workflow_id, record_id=None, context=None,
                         workspace_id=None, initiated_by=None,
                         parent_run_id=None, trigger_type=None) -> WorkflowRun:
        wf = WorkflowDefinition.objects.get(id=workflow_id)
        ws = workspace_id or wf.workspace_id
        if wf.max_concurrent_runs:
            running = WorkflowRun.objects.filter(
                workflow_id=wf.id, status="running").count()
            if running >= wf.max_concurrent_runs:
                raise WorkflowConcurrencyError(
                    f"Workflow {wf.slug!r} at max_concurrent_runs ({wf.max_concurrent_runs})")
        ctx = dict(context or {})
        if parent_run_id:
            ctx["__parent_run_id__"] = str(parent_run_id)
        run = WorkflowRun.objects.create(
            workflow_id=wf.id, workspace_id=ws,
            trigger_type=trigger_type or wf.trigger_type, trigger_payload=ctx,
            entity_id=wf.entity_id,
            record_id=uuid.UUID(str(record_id)) if record_id else None,
            status="running", started_at=_now(), context=ctx,
            initiated_by=uuid.UUID(str(initiated_by)) if initiated_by else None)
        WorkflowDefinition.objects.filter(id=wf.id).update(
            run_count=F("run_count") + 1, last_run_at=_now())
        emit_workflow_event(event_type="workflow.run.started", workspace_id=ws,
                            run_id=run.id, actor_id=initiated_by,
                            payload={"workflow_id": str(wf.id), "record_id": str(record_id)
                                     if record_id else None})
        entry = WorkflowService._entry_steps(wf)
        if not entry:
            WorkflowService._maybe_complete_run(run)
        else:
            WorkflowService._dispatch_all(run, [s.id for s in entry])
        run.refresh_from_db()
        return run

    # ── graph helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _entry_steps(wf) -> list[WorkflowStep]:
        steps = list(WorkflowStep.objects.filter(workflow_id=wf.id))
        flagged = [s for s in steps if s.is_entry]
        if flagged:
            return flagged
        with_incoming = set(
            WorkflowEdge.objects.filter(workflow_id=wf.id)
            .values_list("target_step_id", flat=True))
        return [s for s in steps if s.id not in with_incoming]

    @staticmethod
    def _next_step_ids(run, step, output) -> list:
        edges = list(WorkflowEdge.objects.filter(
            workflow_id=step.workflow_id, source_step_id=step.id))
        branch = output.get("branch") if isinstance(output, dict) else None
        labeled_for_branch = [
            e for e in edges if e.condition_label and e.condition_label == branch]
        record = _record_view(run, run.context or {})
        targets = []
        for e in edges:
            # Any step that emits a ``branch`` routes by ``condition_label`` — ``condition`` AND the
            # Guard Framework's ``action_guard`` (Gap A) both do (guard branches true/false so edges
            # route confirm/reject). Steps that emit no branch (branch is None) follow every edge.
            if branch is not None:
                if e.condition_label and e.condition_label != branch:
                    continue
                if not e.condition_label and labeled_for_branch:
                    continue  # a labelled edge already matched the branch
            if e.condition_expr and not conditions.evaluate(
                    e.condition_expr, record, workspace_id=run.workspace_id,
                    user_id=run.initiated_by,
                    entity_slug=(run.context or {}).get("entity_slug", "")):
                continue
            targets.append(e.target_step_id)
        return targets

    # ── dispatch ──────────────────────────────────────────────────────────────
    @staticmethod
    def _dispatch_all(run, step_ids: list) -> None:
        """Create all pending step-runs, then enqueue each (eager-safe ordering)."""
        created = []
        for sid in step_ids:
            sr = WorkflowStepRun.objects.create(
                run_id=run.id, step_id=sid, workspace_id=run.workspace_id,
                status="pending")
            created.append((sid, sr.id))
        for sid, srid in created:
            WorkflowService._enqueue(run.id, sid, srid)

    @staticmethod
    def dispatch_step(run_id, step_id) -> WorkflowStepRun:
        run = WorkflowRun.objects.get(id=run_id)
        sr = WorkflowStepRun.objects.create(
            run_id=run.id, step_id=step_id, workspace_id=run.workspace_id,
            status="pending")
        WorkflowService._enqueue(run.id, step_id, sr.id)
        return sr

    @staticmethod
    def _enqueue(run_id, step_id, step_run_id) -> None:
        from .tasks import execute_workflow_step
        execute_workflow_step.delay(str(run_id), str(step_id), str(step_run_id))

    # ── step execution (called from the Celery task) ─────────────────────────
    @staticmethod
    def run_step(run_id, step_id, step_run_id) -> None:
        run = WorkflowRun.objects.get(id=run_id)
        step = WorkflowStep.objects.get(id=step_id)
        sr = WorkflowStepRun.objects.get(id=step_run_id)
        if run.status != "running":
            sr.status = "skipped"
            sr.save(update_fields=["status"])
            return
        ctx = run.context or {}
        ctx["__step_run_id__"] = str(sr.id)
        member = member_for_run(run)
        executor = get_executor(step.step_type)
        max_retries = WorkflowService._max_retries(run, step)
        attempt = sr.attempt_number or 1
        output = None
        while True:
            try:
                sr.status = "running"
                sr.started_at = sr.started_at or _now()
                sr.attempt_number = attempt
                sr.save(update_fields=["status", "started_at", "attempt_number"])
                output = executor(step, run, ctx, member)
                break
            except Exception as exc:  # noqa: BLE001 — engine boundary
                if attempt <= max_retries:
                    attempt += 1
                    sr.error_message = str(exc)
                    sr.save(update_fields=["error_message"])
                    continue
                ctx.pop("__step_run_id__", None)
                run.context = ctx
                run.save(update_fields=["context"])
                WorkflowService.fail_step(sr.id, str(exc))
                return
        ctx.pop("__step_run_id__", None)
        run.context = ctx
        run.save(update_fields=["context"])
        if isinstance(output, dict) and output.get(HALT_KEY):
            sr.status = "waiting_approval" if step.step_type == "approval" else "running"
            sr.output_data = {k: v for k, v in output.items() if k != HALT_KEY}
            sr.save(update_fields=["status", "output_data"])
            return  # paused; resumed externally (approval decision / wait timer)
        WorkflowService.complete_step(sr.id, output or {})

    @staticmethod
    def _max_retries(run, step) -> int:
        rc = step.retry_config or {}
        if "max_retries" in rc:
            return int(rc["max_retries"])
        rp = WorkflowDefinition.objects.filter(id=run.workflow_id).values_list(
            "retry_policy", flat=True).first() or {}
        return int(rp.get("max_retries", 0))

    # ── completion / failure ──────────────────────────────────────────────────
    @staticmethod
    def complete_step(step_run_id, output_data: dict) -> None:
        sr = WorkflowStepRun.objects.get(id=step_run_id)
        if sr.status == "completed":
            return
        run = WorkflowRun.objects.get(id=sr.run_id)
        step = WorkflowStep.objects.get(id=sr.step_id)
        clean = {k: v for k, v in (output_data or {}).items() if k != HALT_KEY}
        sr.status = "completed"
        sr.completed_at = _now()
        sr.duration_ms = _ms(sr.started_at, sr.completed_at)
        sr.output_data = clean
        sr.save(update_fields=["status", "completed_at", "duration_ms", "output_data"])
        emit_workflow_event(event_type="workflow.step.completed",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=run.initiated_by,
                            payload={"step_id": str(step.id), "step_type": step.step_type,
                                     "output": clean})
        ctx = run.context or {}
        ctx.setdefault("steps", {})[str(step.id)] = clean
        for k, v in clean.items():
            if k not in _CONTROL_KEYS:
                ctx[k] = v
        run.context = ctx
        run.save(update_fields=["context"])
        WorkflowService._advance(run, step, output_data or {})

    @staticmethod
    def fail_step(step_run_id, error: str) -> None:
        sr = WorkflowStepRun.objects.get(id=step_run_id)
        run = WorkflowRun.objects.get(id=sr.run_id)
        step = WorkflowStep.objects.get(id=sr.step_id)
        sr.status = "failed"
        sr.completed_at = _now()
        sr.duration_ms = _ms(sr.started_at, sr.completed_at)
        sr.error_message = error
        sr.save(update_fields=["status", "completed_at", "duration_ms", "error_message"])
        emit_workflow_event(event_type="workflow.step.failed",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=run.initiated_by,
                            payload={"step_id": str(step.id), "error": error})
        if step.on_error == "continue":
            WorkflowService._advance(run, step, {})
            return
        run.status = "failed"
        run.completed_at = _now()
        run.duration_ms = _ms(run.started_at, run.completed_at)
        run.error_message = error
        run.error_step_id = step.id
        run.save(update_fields=["status", "completed_at", "duration_ms",
                                "error_message", "error_step_id"])
        WorkflowDefinition.objects.filter(id=run.workflow_id).update(
            error_count=F("error_count") + 1)
        emit_workflow_event(event_type="workflow.run.failed",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=run.initiated_by,
                            payload={"error": error, "step_id": str(step.id)})

    @staticmethod
    def _advance(run, step, output: dict) -> None:
        next_ids = WorkflowService._next_step_ids(run, step, output)
        to_dispatch = []
        ctx = run.context or {}
        for tid in next_ids:
            target = WorkflowStep.objects.get(id=tid)
            if target.step_type == "join":
                in_degree = WorkflowEdge.objects.filter(
                    workflow_id=step.workflow_id, target_step_id=tid).count()
                joins = ctx.setdefault("__joins", {})
                joins[str(tid)] = joins.get(str(tid), 0) + 1
                if joins[str(tid)] < in_degree:
                    continue  # wait for the remaining branches
            to_dispatch.append(tid)
        run.context = ctx
        run.save(update_fields=["context"])
        if not to_dispatch:
            WorkflowService._maybe_complete_run(run)
            return
        WorkflowService._dispatch_all(run, to_dispatch)

    @staticmethod
    def _maybe_complete_run(run) -> None:
        run.refresh_from_db()
        if run.status != "running":
            return
        if WorkflowStepRun.objects.filter(
                run_id=run.id, status__in=_ACTIVE_STEP_STATES).exists():
            return
        run.status = "completed"
        run.completed_at = _now()
        run.duration_ms = _ms(run.started_at, run.completed_at)
        run.save(update_fields=["status", "completed_at", "duration_ms"])
        emit_workflow_event(event_type="workflow.run.completed",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=run.initiated_by, payload={})

    # ── external resume hooks ─────────────────────────────────────────────────
    @staticmethod
    def resume_after_wait(run_id, step_run_id) -> None:
        sr = WorkflowStepRun.objects.filter(id=step_run_id).first()
        if sr is None or sr.status == "completed":
            return
        run = WorkflowRun.objects.get(id=sr.run_id)
        if run.status != "running":
            return
        WorkflowService.complete_step(sr.id, {"resumed": True})

    @staticmethod
    def resume_approval(step_run_id, *, approved: bool, comment: str = "") -> None:
        sr = WorkflowStepRun.objects.filter(id=step_run_id).first()
        if sr is None or sr.status not in ("waiting_approval", "running", "pending"):
            return
        if approved:
            WorkflowService.complete_step(sr.id, {"approved": True, "comment": comment})
        else:
            WorkflowService.fail_step(sr.id, comment or "Approval rejected")

    # ── cancel / retry ────────────────────────────────────────────────────────
    @staticmethod
    def cancel_run(run_id, *, actor_id=None, reason="cancelled") -> WorkflowRun:
        run = WorkflowRun.objects.get(id=run_id)
        if run.status in ("completed", "failed", "cancelled", "timed_out"):
            return run
        with transaction.atomic():
            WorkflowStepRun.objects.filter(
                run_id=run.id, status__in=_ACTIVE_STEP_STATES).update(status="skipped")
            run.status = "cancelled"
            run.completed_at = _now()
            run.duration_ms = _ms(run.started_at, run.completed_at)
            run.error_message = reason
            run.save(update_fields=["status", "completed_at", "duration_ms", "error_message"])
        emit_workflow_event(event_type="workflow.run.cancelled",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=actor_id, payload={"reason": reason})
        return run

    @staticmethod
    def retry_run(run_id, *, actor_id=None) -> WorkflowRun:
        """Re-run a failed/cancelled run from the beginning as a fresh run."""
        old = WorkflowRun.objects.get(id=run_id)
        return WorkflowService.trigger_workflow(
            workflow_id=old.workflow_id, record_id=old.record_id,
            context=dict(old.trigger_payload or {}), workspace_id=old.workspace_id,
            initiated_by=actor_id or old.initiated_by, trigger_type=old.trigger_type)

    # ── trigger evaluation ────────────────────────────────────────────────────
    @staticmethod
    def evaluate_trigger(workflow, event_type: str, record: dict) -> bool:
        if workflow.status != "active":
            return False
        if workflow.trigger_type != event_type:
            return False
        cfg = workflow.trigger_config or {}
        # entity scoping (slug or id)
        wanted_slug = cfg.get("entity_slug")
        if wanted_slug and record.get("entity_slug") and wanted_slug != record.get("entity_slug"):
            return False
        # field_changed: require one of the named fields to have changed
        if event_type == "field_changed":
            watched = cfg.get("fields") or []
            changed = set(record.get("__changed_fields__") or [])
            if watched and not (set(watched) & changed):
                return False
        cond = cfg.get("condition")
        if cond:
            return conditions.evaluate(
                cond, record, workspace_id=workflow.workspace_id,
                user_id=record.get("__actor_id__"),
                entity_slug=record.get("entity_slug", ""))
        return True
