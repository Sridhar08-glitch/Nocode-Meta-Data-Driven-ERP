"""
Celery tasks for the workflow engine (PROJECT_HANDBOOK.md §21.3 / §21.6).

Under the test harness Celery runs eager (``task_always_eager``) so these execute
synchronously and the whole graph resolves in-process.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from celery import shared_task

from .cron import cron_is_due
from .events import emit_workflow_event
from .models import WorkflowDefinition, WorkflowRun, WorkflowStepRun
from .services import WorkflowService

_ACTIVE_STEP_STATES = ("pending", "running", "waiting_approval")


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name="workflows.execute_workflow_step")
def execute_workflow_step(self, run_id: str, step_id: str, step_run_id: str) -> None:
    """Execute a single step. Retries are handled inside ``run_step`` so behaviour is
    identical under eager and async Celery."""
    WorkflowService.run_step(run_id, step_id, step_run_id)


@shared_task(name="workflows.resume_workflow_after_wait")
def resume_workflow_after_wait(run_id: str, step_run_id: str) -> None:
    """Resume a run paused on a ``wait`` step (scheduled via ETA)."""
    WorkflowService.resume_after_wait(run_id, step_run_id)


@shared_task(name="workflows.cancel_stalled_runs")
def cancel_stalled_runs() -> dict:
    """Beat task: fail runs stuck in ``running`` for more than 24h."""
    cutoff = timezone.now() - timedelta(hours=24)
    stalled = WorkflowRun.objects.filter(status="running", started_at__lt=cutoff)
    count = 0
    for run in stalled:
        WorkflowStepRun.objects.filter(
            run_id=run.id, status__in=_ACTIVE_STEP_STATES).update(status="skipped")
        run.status = "timed_out"
        run.completed_at = timezone.now()
        run.error_message = "timeout"
        run.save(update_fields=["status", "completed_at", "error_message"])
        WorkflowDefinition.objects.filter(id=run.workflow_id).update()
        emit_workflow_event(event_type="workflow.run.failed",
                            workspace_id=run.workspace_id, run_id=run.id,
                            actor_id=run.initiated_by, payload={"error": "timeout"})
        count += 1
    return {"timed_out": count}


@shared_task(name="workflows.fire_scheduled_workflows")
def fire_scheduled_workflows() -> dict:
    """Beat task: fire any ``schedule``-triggered workflow whose CRON is due."""
    now = timezone.now()
    fired = []
    for wf in WorkflowDefinition.objects.filter(trigger_type="schedule", status="active"):
        cron = (wf.trigger_config or {}).get("cron")
        if not cron:
            continue
        try:
            due = cron_is_due(cron, wf.last_run_at, now)
        except ValueError:
            continue
        if due:
            WorkflowService.trigger_workflow(
                workflow_id=wf.id, context={"scheduled_at": now.isoformat()},
                workspace_id=wf.workspace_id, trigger_type="schedule")
            fired.append(str(wf.id))
    return {"fired": fired}
