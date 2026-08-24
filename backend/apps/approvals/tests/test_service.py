"""ApprovalService (PROJECT_HANDBOOK.md §27.1 / §27.4)."""
import pytest

from apps.approvals.services import (
    ApprovalPermissionError,
    ApprovalService,
)
from apps.eventstore.models import DomainEvent
from apps.notifications.models import Notification


def _member_level(*user_ids, quorum="any", timeout_hours=None, on_timeout="auto_reject", level=1):
    cfg = {"level": level, "quorum": quorum,
           "approvers": [{"type": "member", "value": str(u)} for u in user_ids]}
    if timeout_hours is not None:
        cfg["timeout_hours"] = timeout_hours
        cfg["on_timeout"] = on_timeout
    return cfg


@pytest.mark.django_db
class TestCreate:
    def test_notifies_and_emits(self, ws, requester, approver_a, make_process, record_id):
        process = make_process([_member_level(approver_a.id, timeout_hours=24)])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        assert req.status == "pending" and req.current_level == 1
        assert req.expires_at is not None
        assert Notification.objects.filter(recipient_id=approver_a.id).exists()
        assert DomainEvent.objects.filter(
            aggregate_id=req.id, event_type="approval.requested").exists()


@pytest.mark.django_db
class TestQuorum:
    def test_any_first_approve_passes(self, ws, requester, approver_a, approver_b,
                                      make_process, record_id):
        process = make_process([_member_level(approver_a.id, approver_b.id, quorum="any")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.approve(req.id, approver_a.id)
        assert req.status == "approved"

    def test_all_requires_every_approver(self, ws, requester, approver_a, approver_b,
                                         make_process, record_id):
        process = make_process([_member_level(approver_a.id, approver_b.id, quorum="all")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.approve(req.id, approver_a.id)
        assert req.status == "pending"            # B still outstanding
        req = ApprovalService.approve(req.id, approver_b.id)
        assert req.status == "approved"


@pytest.mark.django_db
class TestMultiLevel:
    def test_advances_levels(self, ws, requester, approver_a, approver_b,
                             make_process, record_id):
        process = make_process([
            _member_level(approver_a.id, level=1),
            _member_level(approver_b.id, level=2)])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.approve(req.id, approver_a.id)
        assert req.status == "pending" and req.current_level == 2
        # the level-1 approver cannot approve level 2
        with pytest.raises(ApprovalPermissionError):
            ApprovalService.approve(req.id, approver_a.id)
        req = ApprovalService.approve(req.id, approver_b.id)
        assert req.status == "approved"


@pytest.mark.django_db
class TestReject:
    def test_reject_is_immediate(self, ws, requester, approver_a, approver_b,
                                 make_process, record_id):
        process = make_process([_member_level(approver_a.id, approver_b.id, quorum="all")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.reject(req.id, approver_a.id, "no")
        assert req.status == "rejected"

    def test_non_approver_cannot_approve(self, ws, requester, approver_a, approver_b,
                                         make_process, record_id):
        process = make_process([_member_level(approver_a.id)])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        with pytest.raises(ApprovalPermissionError):
            ApprovalService.approve(req.id, approver_b.id)


@pytest.mark.django_db
class TestCancel:
    def test_requester_can_cancel(self, ws, requester, approver_a, make_process, record_id):
        process = make_process([_member_level(approver_a.id)])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.cancel(req.id, requester.id)
        assert req.status == "cancelled"


@pytest.mark.django_db
class TestRoleApprover:
    def test_role_resolves_members(self, ws, requester, approver_a, make_process, record_id):
        # approver_a is a "member" role; level uses type=role
        process = make_process([{"level": 1, "quorum": "any",
                                 "approvers": [{"type": "role", "value": "member"}]}])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        req = ApprovalService.approve(req.id, approver_a.id)
        assert req.status == "approved"
