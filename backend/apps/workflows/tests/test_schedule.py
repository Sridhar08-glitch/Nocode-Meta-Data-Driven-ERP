"""Scheduled execution + stalled-run cancellation (PROJECT_HANDBOOK.md §21.6 / §21.9)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.workflows.models import WorkflowRun, WorkflowStepRun
from apps.workflows.tasks import cancel_stalled_runs, fire_scheduled_workflows


@pytest.mark.django_db
class TestScheduledWorkflows:
    def test_fire_due_schedule(self, ws, lead, make_workflow, add_step):
        wf = make_workflow(trigger_type="schedule", entity_id=lead.id,
                           trigger_config={"cron": "* * * * *"})
        add_step(wf, "transform", "t", {"mappings": {"flag": "1"}}, is_entry=True)
        result = fire_scheduled_workflows()
        assert str(wf.id) in result["fired"]
        assert WorkflowRun.objects.filter(workflow_id=wf.id, status="completed").count() == 1

    def test_non_schedule_not_fired(self, ws, lead, make_workflow, add_step):
        wf = make_workflow(trigger_type="manual", entity_id=lead.id)
        add_step(wf, "transform", "t", is_entry=True)
        result = fire_scheduled_workflows()
        assert str(wf.id) not in result["fired"]

    def test_inactive_schedule_not_fired(self, ws, make_workflow):
        wf = make_workflow(trigger_type="schedule", status="paused",
                           trigger_config={"cron": "* * * * *"})
        result = fire_scheduled_workflows()
        assert str(wf.id) not in result["fired"]


@pytest.mark.django_db
class TestCancelStalled:
    def test_old_running_run_timed_out(self, ws, lead):
        old = timezone.now() - timedelta(hours=30)
        run = WorkflowRun.objects.create(
            workflow_id=lead.id, workspace_id=ws.id, trigger_type="manual",
            status="running", started_at=old)
        WorkflowStepRun.objects.create(run_id=run.id, step_id=lead.id,
                                       workspace_id=ws.id, status="running")
        result = cancel_stalled_runs()
        assert result["timed_out"] == 1
        run.refresh_from_db()
        assert run.status == "timed_out"
        assert run.error_message == "timeout"
        assert WorkflowStepRun.objects.filter(run_id=run.id, status="skipped").count() == 1

    def test_recent_run_untouched(self, ws, lead):
        run = WorkflowRun.objects.create(
            workflow_id=lead.id, workspace_id=ws.id, trigger_type="manual",
            status="running", started_at=timezone.now())
        result = cancel_stalled_runs()
        assert result["timed_out"] == 0
        run.refresh_from_db()
        assert run.status == "running"
