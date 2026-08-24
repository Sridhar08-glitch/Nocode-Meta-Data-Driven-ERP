"""WorkflowService — graph execution lifecycle (PROJECT_HANDBOOK.md §21.9)."""
import pytest

from apps.eventstore.models import DomainEvent
from apps.records.services import RecordService
from apps.workflows import executors
from apps.workflows.models import WorkflowRun, WorkflowStepRun
from apps.workflows.services import WorkflowConcurrencyError, WorkflowService


@pytest.mark.django_db
class TestLinearExecution:
    def test_linear_chain_runs_in_order(self, ws, member, lead, make_workflow,
                                        add_step, add_edge, make_lead_record):
        rec = make_lead_record(name="L", status="new")
        wf = make_workflow(trigger_type="manual", entity_id=lead.id)
        s1 = add_step(wf, "action_set_field", "s1",
                      {"field": "status", "value": "step1"}, is_entry=True)
        s2 = add_step(wf, "action_set_field", "s2", {"field": "status", "value": "step2"})
        s3 = add_step(wf, "action_set_field", "s3", {"field": "status", "value": "step3"})
        add_edge(wf, s1, s2)
        add_edge(wf, s2, s3)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)

        assert run.status == "completed"
        srs = WorkflowStepRun.objects.filter(run_id=run.id)
        assert srs.count() == 3
        assert all(sr.status == "completed" for sr in srs)
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "step3"   # last step in the chain won

    def test_run_started_and_completed_events_emitted(self, ws, member, lead,
                                                      make_workflow, add_step,
                                                      make_lead_record):
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        add_step(wf, "transform", "t", {"mappings": {"flag": "1"}}, is_entry=True)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        types = set(DomainEvent.objects.filter(aggregate_id=run.id)
                    .values_list("event_type", flat=True))
        assert "workflow.run.started" in types
        assert "workflow.run.completed" in types
        assert "workflow.step.completed" in types


@pytest.mark.django_db
class TestBranching:
    def _branch_wf(self, lead, make_workflow, add_step, add_edge):
        wf = make_workflow(entity_id=lead.id)
        cond = add_step(wf, "condition", "c", {"condition_nql": "value > 100"}, is_entry=True)
        big = add_step(wf, "action_set_field", "big", {"field": "status", "value": "big"})
        small = add_step(wf, "action_set_field", "small", {"field": "status", "value": "small"})
        add_edge(wf, cond, big, label="true")
        add_edge(wf, cond, small, label="false")
        return wf, big, small

    def test_true_branch(self, ws, member, lead, make_workflow, add_step, add_edge,
                         make_lead_record):
        rec = make_lead_record(value=200)
        wf, big, small = self._branch_wf(lead, make_workflow, add_step, add_edge)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        assert run.status == "completed"
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "big"
        # the false-branch step never created a step run
        assert not WorkflowStepRun.objects.filter(run_id=run.id, step_id=small.id).exists()

    def test_false_branch(self, ws, member, lead, make_workflow, add_step, add_edge,
                          make_lead_record):
        rec = make_lead_record(value=50)
        wf, big, small = self._branch_wf(lead, make_workflow, add_step, add_edge)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "small"
        assert not WorkflowStepRun.objects.filter(run_id=run.id, step_id=big.id).exists()


@pytest.mark.django_db
class TestParallelJoin:
    def test_parallel_split_and_join(self, ws, member, lead, make_workflow,
                                     add_step, add_edge, make_lead_record):
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        p = add_step(wf, "parallel", "p", is_entry=True)
        a = add_step(wf, "transform", "a", {"mappings": {"a_done": "1"}})
        b = add_step(wf, "transform", "b", {"mappings": {"b_done": "1"}})
        j = add_step(wf, "join", "j")
        f = add_step(wf, "action_set_field", "f", {"field": "status", "value": "joined"})
        add_edge(wf, p, a)
        add_edge(wf, p, b)
        add_edge(wf, a, j)
        add_edge(wf, b, j)
        add_edge(wf, j, f)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)

        assert run.status == "completed"
        # both branches ran, join ran exactly once, final step ran
        assert WorkflowStepRun.objects.filter(run_id=run.id, step_id=a.id).count() == 1
        assert WorkflowStepRun.objects.filter(run_id=run.id, step_id=b.id).count() == 1
        assert WorkflowStepRun.objects.filter(run_id=run.id, step_id=j.id).count() == 1
        assert WorkflowStepRun.objects.filter(run_id=run.id, step_id=f.id).count() == 1
        run.refresh_from_db()
        assert run.context.get("a_done") == 1
        assert run.context.get("b_done") == 1
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "joined"


@pytest.mark.django_db
class TestRetry:
    def test_step_fails_until_retries_exhausted(self, ws, member, lead, make_workflow,
                                                add_step, make_lead_record, monkeypatch):
        calls = {"n": 0}

        def boom(step, run, ctx, member):
            calls["n"] += 1
            raise executors.ExecutorError("kaboom")

        monkeypatch.setitem(executors.REGISTRY, "transform", boom)
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id, retry_policy={"max_retries": 2})
        add_step(wf, "transform", "t", {"mappings": {}}, is_entry=True)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)

        assert run.status == "failed"
        assert calls["n"] == 3   # 1 initial + 2 retries
        sr = WorkflowStepRun.objects.get(run_id=run.id)
        assert sr.status == "failed"
        assert sr.attempt_number == 3
        types = set(DomainEvent.objects.filter(aggregate_id=run.id)
                    .values_list("event_type", flat=True))
        assert "workflow.step.failed" in types
        assert "workflow.run.failed" in types

    def test_on_error_continue_advances(self, ws, member, lead, make_workflow,
                                        add_step, add_edge, make_lead_record, monkeypatch):
        def boom(step, run, ctx, member):
            raise executors.ExecutorError("ignore me")

        monkeypatch.setitem(executors.REGISTRY, "nql_query", boom)
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        s1 = add_step(wf, "nql_query", "s1", {"nql": {"entity": "lead"}},
                      is_entry=True, on_error="continue")
        s2 = add_step(wf, "action_set_field", "s2", {"field": "status", "value": "after"})
        add_edge(wf, s1, s2)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)

        assert run.status == "completed"   # failure was tolerated
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "after"


@pytest.mark.django_db
class TestWaitResume:
    def test_wait_then_resume(self, ws, member, lead, make_workflow, add_step,
                              add_edge, make_lead_record):
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        w = add_step(wf, "action_wait", "w", {"seconds": 0}, is_entry=True)
        s2 = add_step(wf, "action_set_field", "s2", {"field": "status", "value": "resumed"})
        add_edge(wf, w, s2)
        # eager celery executes the ETA resume task immediately
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        assert run.status == "completed"
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "resumed"


@pytest.mark.django_db
class TestApproval:
    def _approval_wf(self, lead, make_workflow, add_step, add_edge):
        wf = make_workflow(entity_id=lead.id)
        ap = add_step(wf, "approval", "ap", {"process_id": None}, is_entry=True)
        done = add_step(wf, "action_set_field", "done",
                        {"field": "status", "value": "approved"})
        add_edge(wf, ap, done)
        return wf, ap, done

    def test_approval_halts_then_approve_resumes(self, ws, member, lead, make_workflow,
                                                 add_step, add_edge, make_lead_record):
        rec = make_lead_record()
        wf, ap, done = self._approval_wf(lead, make_workflow, add_step, add_edge)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        assert run.status == "running"   # halted on approval
        ap_run = WorkflowStepRun.objects.get(run_id=run.id, step_id=ap.id)
        assert ap_run.status == "waiting_approval"
        assert not WorkflowStepRun.objects.filter(run_id=run.id, step_id=done.id).exists()

        WorkflowService.resume_approval(ap_run.id, approved=True)
        run.refresh_from_db()
        assert run.status == "completed"
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "approved"

    def test_approval_reject_fails_run(self, ws, member, lead, make_workflow,
                                       add_step, add_edge, make_lead_record):
        rec = make_lead_record()
        wf, ap, done = self._approval_wf(lead, make_workflow, add_step, add_edge)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        ap_run = WorkflowStepRun.objects.get(run_id=run.id, step_id=ap.id)
        WorkflowService.resume_approval(ap_run.id, approved=False, comment="nope")
        run.refresh_from_db()
        assert run.status == "failed"


@pytest.mark.django_db
class TestCancel:
    def test_cancel_halted_run(self, ws, member, lead, make_workflow, add_step,
                               add_edge, make_lead_record):
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        ap = add_step(wf, "approval", "ap", is_entry=True)
        done = add_step(wf, "action_set_field", "done", {"field": "status", "value": "x"})
        add_edge(wf, ap, done)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        ap_run = WorkflowStepRun.objects.get(run_id=run.id, step_id=ap.id)

        WorkflowService.cancel_run(run.id, actor_id=member.user_id)
        run.refresh_from_db()
        assert run.status == "cancelled"
        ap_run.refresh_from_db()
        assert ap_run.status == "skipped"
        # resuming a cancelled run does nothing
        WorkflowService.resume_approval(ap_run.id, approved=True)
        assert not WorkflowStepRun.objects.filter(run_id=run.id, step_id=done.id).exists()


@pytest.mark.django_db
class TestConcurrency:
    def test_max_concurrent_runs_enforced(self, ws, lead, make_workflow, add_step):
        wf = make_workflow(entity_id=lead.id, max_concurrent_runs=1)
        # a step that halts so the first run stays "running"
        add_step(wf, "approval", "ap", is_entry=True)
        WorkflowService.trigger_workflow(workflow_id=wf.id, workspace_id=ws.id)
        with pytest.raises(WorkflowConcurrencyError):
            WorkflowService.trigger_workflow(workflow_id=wf.id, workspace_id=ws.id)


@pytest.mark.django_db
class TestEvaluateTrigger:
    def test_status_and_type_and_condition(self, ws, lead, make_workflow):
        wf = make_workflow(trigger_type="record_created", status="active",
                           trigger_config={"condition": "value > 100"})
        assert WorkflowService.evaluate_trigger(wf, "record_created", {"value": 200})
        assert not WorkflowService.evaluate_trigger(wf, "record_created", {"value": 5})
        assert not WorkflowService.evaluate_trigger(wf, "record_updated", {"value": 200})
        wf.status = "paused"
        assert not WorkflowService.evaluate_trigger(wf, "record_created", {"value": 200})

    def test_entity_scope(self, ws, make_workflow):
        wf = make_workflow(trigger_type="record_created",
                           trigger_config={"entity_slug": "lead"})
        assert WorkflowService.evaluate_trigger(
            wf, "record_created", {"entity_slug": "lead"})
        assert not WorkflowService.evaluate_trigger(
            wf, "record_created", {"entity_slug": "deal"})


@pytest.mark.django_db
class TestRetryRun:
    def test_retry_creates_new_run(self, ws, member, lead, make_workflow, add_step,
                                   make_lead_record, monkeypatch):
        def boom(step, run, ctx, member):
            raise executors.ExecutorError("fail")

        monkeypatch.setitem(executors.REGISTRY, "transform", boom)
        rec = make_lead_record()
        wf = make_workflow(entity_id=lead.id)
        add_step(wf, "transform", "t", is_entry=True)
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=member.user_id)
        assert run.status == "failed"
        new_run = WorkflowService.retry_run(run.id, actor_id=member.user_id)
        assert new_run.id != run.id
        assert WorkflowRun.objects.filter(workflow_id=wf.id).count() == 2
