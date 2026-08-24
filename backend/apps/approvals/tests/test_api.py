"""Approvals REST API + workflow integration (PROJECT_HANDBOOK.md §27.3 / §27.4)."""
import pytest

from apps.approvals.models import ApprovalProcess, ApprovalRequest
from apps.approvals.services import ApprovalService

from .conftest import client_for

BASE = "/api/v1/approvals"


def _level(*uids):
    return {"level": 1, "quorum": "any",
            "approvers": [{"type": "member", "value": str(u)} for u in uids]}


@pytest.mark.django_db
class TestProcessApi:
    def test_crud(self, ws, requester, approver_a):
        c = client_for(ws, requester)
        from apps.schema_registry.services import SchemaRegistryService
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="L", plural_name="Ls")
        r = c.post(f"{BASE}/processes/",
                   {"name": "P", "slug": "p", "entity_id": str(ent.id),
                    "levels": [_level(approver_a.id)]}, format="json")
        assert r.status_code == 201, r.content
        pid = r.json()["id"]
        assert c.get(f"{BASE}/processes/").json()["count"] == 1
        assert c.delete(f"{BASE}/processes/{pid}/").status_code == 204


@pytest.mark.django_db
class TestRequestApi:
    def _process(self, ws, lead, *uids):
        return ApprovalProcess.objects.create(
            workspace_id=ws.id, name="P", slug="p", entity_id=lead.id,
            levels=[_level(*uids)])

    def test_approve_flow(self, ws, requester, approver_a, lead, record_id):
        process = self._process(ws, lead, approver_a.id)
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        c = client_for(ws, approver_a)
        r = c.post(f"{BASE}/requests/{req.id}/approve/", {"comment": "ok"}, format="json")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_reject_flow(self, ws, requester, approver_a, lead, record_id):
        process = self._process(ws, lead, approver_a.id)
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        c = client_for(ws, approver_a)
        assert c.post(f"{BASE}/requests/{req.id}/reject/").json()["status"] == "rejected"

    def test_non_approver_gets_403(self, ws, requester, approver_a, approver_b, lead, record_id):
        process = self._process(ws, lead, approver_a.id)
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        c = client_for(ws, approver_b)
        assert c.post(f"{BASE}/requests/{req.id}/approve/").status_code == 403

    def test_pending_for_me(self, ws, requester, approver_a, lead, record_id):
        process = self._process(ws, lead, approver_a.id)
        ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        c = client_for(ws, approver_a)
        assert c.get(f"{BASE}/requests/pending-for-me/").json()["count"] == 1
        # requester is not an approver → nothing pending for them
        assert client_for(ws, requester).get(
            f"{BASE}/requests/pending-for-me/").json()["count"] == 0


@pytest.mark.django_db
class TestWorkflowIntegration:
    def test_approval_step_halts_then_resumes(self, ws, requester, approver_a, lead):
        from apps.records.services import RecordService
        from apps.tenancy.models import WorkspaceMember
        from apps.workflows.models import WorkflowDefinition, WorkflowEdge, WorkflowStep
        from apps.workflows.services import WorkflowService

        member = WorkspaceMember.objects.get(workspace=ws, user=requester)
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"status": "new"})
        process = ApprovalProcess.objects.create(
            workspace_id=ws.id, name="P", slug="p", entity_id=lead.id,
            levels=[_level(approver_a.id)])
        wf = WorkflowDefinition.objects.create(
            workspace_id=ws.id, name="W", slug="w", trigger_type="manual",
            entity_id=lead.id, status="active")
        ap = WorkflowStep.objects.create(
            workflow_id=wf.id, workspace_id=ws.id, step_type="approval", name="ap",
            config={"process_id": str(process.id)}, is_entry=True)
        done = WorkflowStep.objects.create(
            workflow_id=wf.id, workspace_id=ws.id, step_type="action_set_field", name="done",
            config={"field": "status", "value": "approved"})
        WorkflowEdge.objects.create(workflow_id=wf.id, workspace_id=ws.id,
                                    source_step_id=ap.id, target_step_id=done.id)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=requester.id)
        assert run.status == "running"   # halted on approval
        req = ApprovalRequest.objects.get(workflow_run_id=run.id)
        assert req.step_run_id is not None

        ApprovalService.approve(req.id, approver_a.id)
        run.refresh_from_db()
        assert run.status == "completed"
        updated = RecordService.retrieve_record(
            workspace_id=ws.id, member=member, entity=lead, record_id=rec["id"])
        assert updated["status"] == "approved"

    def test_reject_fails_workflow(self, ws, requester, approver_a, lead):
        from apps.records.services import RecordService
        from apps.tenancy.models import WorkspaceMember
        from apps.workflows.models import WorkflowDefinition, WorkflowStep
        from apps.workflows.services import WorkflowService

        member = WorkspaceMember.objects.get(workspace=ws, user=requester)
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"status": "new"})
        process = ApprovalProcess.objects.create(
            workspace_id=ws.id, name="P2", slug="p2", entity_id=lead.id,
            levels=[_level(approver_a.id)])
        wf = WorkflowDefinition.objects.create(
            workspace_id=ws.id, name="W2", slug="w2", trigger_type="manual",
            entity_id=lead.id, status="active")
        WorkflowStep.objects.create(
            workflow_id=wf.id, workspace_id=ws.id, step_type="approval", name="ap",
            config={"process_id": str(process.id)}, is_entry=True)

        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=rec["id"], context={"record": rec},
            workspace_id=ws.id, initiated_by=requester.id)
        req = ApprovalRequest.objects.get(workflow_run_id=run.id)
        ApprovalService.reject(req.id, approver_a.id, "no")
        run.refresh_from_db()
        assert run.status == "failed"
