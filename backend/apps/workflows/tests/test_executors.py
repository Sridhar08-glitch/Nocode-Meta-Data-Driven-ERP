"""Step executors tested in isolation (PROJECT_HANDBOOK.md §21.9)."""
import pytest

from apps.eventstore.models import DomainEvent
from apps.records.services import RecordService
from apps.workflows import executors
from apps.workflows.executors import HALT_KEY, _InlineStep, member_for_run
from apps.workflows.models import WorkflowRun, WorkflowStep


def _run(ws, lead, member, record_id=None, context=None):
    return WorkflowRun.objects.create(
        workflow_id=lead.id, workspace_id=ws.id, trigger_type="manual",
        entity_id=lead.id, record_id=record_id, status="running",
        context=context or {}, initiated_by=member.user_id)


def _step(ws, lead, step_type, config=None):
    return WorkflowStep.objects.create(
        workflow_id=lead.id, workspace_id=ws.id, step_type=step_type,
        name=step_type, config=config or {})


@pytest.mark.django_db
class TestRecordExecutors:
    def test_create_record(self, ws, lead, member):
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_create_record",
                     {"entity_slug": "lead", "data": {"name": "New", "status": "open"}})
        out = executors.exec_create_record(step, run, run.context, member_for_run(run))
        assert out["created_id"]
        rec = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=out["created_id"])
        assert rec["name"] == "New"

    def test_update_and_set_field(self, ws, lead, member, make_lead_record):
        rec = make_lead_record(status="old")
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "action_set_field", {"field": "status", "value": "new"})
        executors.exec_set_field(step, run, run.context, member_for_run(run))
        got = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert got["status"] == "new"

    def test_assign(self, ws, lead, member, make_lead_record):
        rec = make_lead_record()
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "action_assign",
                     {"field": "assigned_to", "value": "@me"})
        out = executors.exec_assign(step, run, run.context, member_for_run(run))
        assert out["assignee"] == str(member.user_id)

    def test_add_tag(self, ws, lead, member, make_lead_record):
        from apps.tagging.models import RecordTag
        rec = make_lead_record()
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "action_add_tag", {"tag_slug": "vip", "tag_name": "VIP"})
        out = executors.exec_add_tag(step, run, run.context, member_for_run(run))
        assert out["tag_slug"] == "vip"
        assert RecordTag.objects.filter(workspace_id=ws.id, record_id=rec["id"]).exists()

    def test_delete_record(self, ws, lead, member, make_lead_record):
        rec = make_lead_record()
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "action_delete_record", {})
        out = executors.exec_delete_record(step, run, run.context, member_for_run(run))
        assert out["deleted_id"] == str(rec["id"])

    def test_stage_transition_emits_event(self, ws, lead, member, make_lead_record):
        rec = make_lead_record(stage="new")
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "stage_transition",
                     {"stage_field": "stage", "to_stage": "qualified"})
        executors.exec_stage_transition(step, run, run.context, member_for_run(run))
        got = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert got["stage"] == "qualified"
        assert DomainEvent.objects.filter(
            event_type="record.stage_entered", aggregate_id=run.id).exists()


@pytest.mark.django_db
class TestControlExecutors:
    def test_condition_true_false(self, ws, lead, member):
        run = _run(ws, lead, member, context={"record": {"value": 200}})
        step = _step(ws, lead, "condition", {"condition_nql": "value > 100"})
        assert executors.exec_condition(step, run, run.context, member_for_run(run))["branch"] == "true"
        run2 = _run(ws, lead, member, context={"record": {"value": 5}})
        assert executors.exec_condition(step, run2, run2.context, member_for_run(run2))["branch"] == "false"

    def test_transform_and_run_script(self, ws, lead, member):
        run = _run(ws, lead, member, context={"record": {"qty": 3, "price": 4}})
        t = _step(ws, lead, "transform", {"mappings": {"total": "qty * price"}})
        out = executors.exec_transform(t, run, run.context, member_for_run(run))
        assert out["transform"]["total"] == 12
        s = _step(ws, lead, "action_run_script", {"assignments": {"double": "qty * 2"}})
        out2 = executors.exec_run_script(s, run, run.context, member_for_run(run))
        assert out2["assignments"]["double"] == 6

    def test_nql_query(self, ws, lead, member, make_lead_record):
        make_lead_record(name="one")
        make_lead_record(name="two")
        run = _run(ws, lead, member)
        step = _step(ws, lead, "nql_query", {"nql": {"entity": "lead"}, "into": "rows"})
        out = executors.exec_nql_query(step, run, run.context, member_for_run(run))
        assert out["count"] == 2
        assert len(run.context["rows"]) == 2

    def test_loop_runs_inner_per_item(self, ws, lead, member):
        run = _run(ws, lead, member, context={"items": [1, 2, 3]})
        step = _step(ws, lead, "loop", {
            "items": "{{items}}",
            "action": {"type": "transform", "config": {"mappings": {"x": "1"}}}})
        out = executors.exec_loop(step, run, run.context, member_for_run(run))
        assert out["iterations"] == 3
        assert len(out["results"]) == 3

    def test_parallel_and_join_markers(self, ws, lead, member):
        run = _run(ws, lead, member)
        p = _step(ws, lead, "parallel")
        j = _step(ws, lead, "join")
        assert executors.exec_parallel(p, run, run.context, member_for_run(run))["branch"] == "parallel"
        assert executors.exec_join(j, run, run.context, member_for_run(run))["joined"] is True

    def test_wait_halts(self, ws, lead, member, monkeypatch):
        scheduled = {}
        monkeypatch.setattr(
            "apps.workflows.tasks.resume_workflow_after_wait.apply_async",
            lambda *a, **k: scheduled.update(k) or scheduled.update({"args": a}))
        run = _run(ws, lead, member, context={"__step_run_id__": "abc"})
        step = _step(ws, lead, "action_wait", {"seconds": 30})
        out = executors.exec_wait(step, run, run.context, member_for_run(run))
        assert out[HALT_KEY] is True
        assert "resume_at" in out

    def test_approval_halts(self, ws, lead, member):
        run = _run(ws, lead, member)
        step = _step(ws, lead, "approval", {"process_id": None})
        out = executors.exec_approval(step, run, run.context, member_for_run(run))
        assert out[HALT_KEY] is True


@pytest.mark.django_db
class TestMessagingExecutors:
    def test_send_notification_dispatches_via_service(self, ws, lead, member):
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_send_notification",
                     {"recipient_id": str(member.user_id), "template_slug": "x"})
        out = executors.exec_send_notification(
            step, run, run.context, member_for_run(run))
        # Phase 1.13 NotificationService is now wired → dispatch succeeds
        assert out["dispatched"] is True
        assert out["channel"] == "in_app"

    def test_send_notification_uses_service_when_present(self, ws, lead, member, monkeypatch):
        sent = {}
        monkeypatch.setattr(
            executors, "_send_notification",
            lambda **kw: sent.update(kw) or {"dispatched": True, "channel": kw["channel"]})
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_send_email",
                     {"recipient_id": str(member.user_id), "template_slug": "welcome"})
        out = executors.exec_send_email(step, run, run.context, member_for_run(run))
        assert out["dispatched"] is True
        assert out["channel"] == "email"

    def test_send_webhook_signs_and_posts(self, ws, lead, member, monkeypatch):
        captured = {}

        def fake_post(url, body, headers, timeout=10):
            captured.update(url=url, body=body, headers=headers)
            return {"status": 200, "body": {}}

        monkeypatch.setattr(executors, "_http_post", fake_post)
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_send_webhook",
                     {"url": "https://hook.example/x", "payload": {"k": "v"},
                      "signing_secret": "s3cr3t"})
        out = executors.exec_send_webhook(step, run, run.context, member_for_run(run))
        assert out["webhook_status"] == 200
        assert captured["headers"]["X-Nexus-Signature"].startswith("sha256=")

    def test_call_api_injects_result(self, ws, lead, member, monkeypatch):
        monkeypatch.setattr(executors, "_http_post",
                            lambda *a, **k: {"status": 201, "body": {"ok": True}})
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_call_api",
                     {"url": "https://api.example/x", "method": "POST",
                      "body": {}, "into": "api_result"})
        out = executors.exec_call_api(step, run, run.context, member_for_run(run))
        assert out["status"] == 201
        assert run.context["api_result"]["body"]["ok"] is True


@pytest.mark.django_db
class TestSubworkflowAndSla:
    def test_run_workflow_triggers_child(self, ws, lead, member, make_workflow, add_step):
        child = make_workflow(entity_id=lead.id)
        add_step(child, "transform", "t", {"mappings": {"done": "1"}}, is_entry=True)
        run = _run(ws, lead, member)
        step = _step(ws, lead, "action_run_workflow", {"workflow_id": str(child.id)})
        out = executors.exec_run_workflow(step, run, run.context, member_for_run(run))
        assert out["child_run_id"]

    def test_sla_pause_applies_via_service(self, ws, lead, member, make_lead_record):
        rec = make_lead_record()
        run = _run(ws, lead, member, record_id=rec["id"])
        step = _step(ws, lead, "sla_pause", {})
        out = executors.exec_sla_pause(step, run, run.context, member_for_run(run))
        # Phase 1.19 SLAService is now wired → pause runs (no SLA records ⇒ applied, empty)
        assert out["applied"] is True


@pytest.mark.django_db
class TestInlineStep:
    def test_inline_step_dataclass(self):
        s = _InlineStep("transform", {"mappings": {}})
        assert s.step_type == "transform"
        assert s.config == {"mappings": {}}
