"""Trigger dispatcher + RecordService integration (PROJECT_HANDBOOK.md §21.4 / §21.9)."""
import pytest
from django.test import TestCase

from apps.records.services import RecordService
from apps.workflows.dispatcher import run_record_event
from apps.workflows.models import WorkflowRun


@pytest.mark.django_db
class TestDispatcherSync:
    def test_run_record_event_fires_matching_workflow(self, ws, lead, make_workflow,
                                                      add_step):
        wf = make_workflow(trigger_type="record_created", entity_id=lead.id)
        add_step(wf, "transform", "t", {"mappings": {"flag": "1"}}, is_entry=True)
        runs = run_record_event(
            event_type="record_created", entity_slug="lead", entity_id=lead.id,
            record_id="00000000-0000-0000-0000-000000000001",
            record={"value": 1, "entity_slug": "lead"}, workspace_id=ws.id)
        assert len(runs) == 1
        run = WorkflowRun.objects.get(id=runs[0])
        assert run.status == "completed"
        assert run.context["flag"] == 1

    def test_condition_filters_dispatch(self, ws, lead, make_workflow, add_step):
        wf = make_workflow(trigger_type="record_created", entity_id=lead.id,
                           trigger_config={"condition": "value > 100"})
        add_step(wf, "transform", "t", {"mappings": {}}, is_entry=True)
        none = run_record_event(
            event_type="record_created", entity_slug="lead", entity_id=lead.id,
            record_id="00000000-0000-0000-0000-000000000002",
            record={"value": 5}, workspace_id=ws.id)
        assert none == []
        fired = run_record_event(
            event_type="record_created", entity_slug="lead", entity_id=lead.id,
            record_id="00000000-0000-0000-0000-000000000003",
            record={"value": 999}, workspace_id=ws.id)
        assert len(fired) == 1

    def test_paused_workflow_not_dispatched(self, ws, lead, make_workflow, add_step):
        wf = make_workflow(trigger_type="record_created", entity_id=lead.id, status="paused")
        add_step(wf, "transform", "t", is_entry=True)
        runs = run_record_event(
            event_type="record_created", entity_slug="lead", entity_id=lead.id,
            record_id="00000000-0000-0000-0000-000000000004",
            record={"value": 1}, workspace_id=ws.id)
        assert runs == []

    def test_workspace_isolation(self, ws, lead, make_workflow, add_step):
        import uuid
        wf = make_workflow(trigger_type="record_created", entity_id=lead.id)
        add_step(wf, "transform", "t", is_entry=True)
        # a different workspace id sees no workflows
        runs = run_record_event(
            event_type="record_created", entity_slug="lead", entity_id=lead.id,
            record_id="00000000-0000-0000-0000-000000000005",
            record={"value": 1}, workspace_id=uuid.uuid4())
        assert runs == []


class TestOnCommitIntegration(TestCase):
    """on_commit callbacks need a real commit — use capture_on_commit_callbacks."""

    def test_create_record_fires_workflow_post_commit(self):
        from apps.accounts.models import User
        from apps.schema_registry.services import SchemaRegistryService
        from apps.tenancy.models import Workspace, WorkspaceMember
        from apps.workflows.models import WorkflowDefinition, WorkflowStep

        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        user = User.objects.create_user(email="c@acme.com", password="Sup3rStr0ng!pw",
                                        is_verified=True)
        member = WorkspaceMember.objects.create(workspace=ws, user=user, role="admin",
                                                status="active")
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead",
                                        slug="status", name="Status",
                                        field_type="text", is_promoted=True)
        ent.refresh_from_db()
        wf = WorkflowDefinition.objects.create(
            workspace_id=ws.id, name="onc", slug="onc", trigger_type="record_created",
            entity_id=ent.id, status="active")
        WorkflowStep.objects.create(workflow_id=wf.id, workspace_id=ws.id,
                                    step_type="transform", name="t",
                                    config={"mappings": {"flag": "1"}}, is_entry=True)

        with self.captureOnCommitCallbacks(execute=True):
            RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                        data={"status": "new"})

        assert WorkflowRun.objects.filter(workflow_id=wf.id, status="completed").count() == 1
