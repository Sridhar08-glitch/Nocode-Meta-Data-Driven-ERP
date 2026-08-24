"""Approval timeout task (PROJECT_HANDBOOK.md §27.2 / §27.4)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.approvals.services import ApprovalService
from apps.approvals.tasks import check_approval_timeout


def _level(*uids, on_timeout, level=1, timeout_hours=1):
    return {"level": level, "quorum": "any", "timeout_hours": timeout_hours,
            "on_timeout": on_timeout,
            "approvers": [{"type": "member", "value": str(u)} for u in uids]}


def _expire(req):
    from apps.approvals.models import ApprovalRequest
    ApprovalRequest.objects.filter(id=req.id).update(
        expires_at=timezone.now() - timedelta(hours=1))


@pytest.mark.django_db
class TestTimeout:
    def test_auto_approve(self, ws, requester, approver_a, make_process, record_id):
        process = make_process([_level(approver_a.id, on_timeout="auto_approve")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        _expire(req)
        counts = check_approval_timeout()
        assert counts["auto_approved"] == 1
        req.refresh_from_db()
        assert req.status == "approved"

    def test_auto_reject(self, ws, requester, approver_a, make_process, record_id):
        process = make_process([_level(approver_a.id, on_timeout="auto_reject")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        _expire(req)
        check_approval_timeout()
        req.refresh_from_db()
        assert req.status == "rejected"

    def test_escalate(self, ws, requester, approver_a, approver_b, make_process, record_id):
        process = make_process([
            _level(approver_a.id, on_timeout="escalate", level=1),
            _level(approver_b.id, on_timeout="auto_reject", level=2)])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        _expire(req)
        counts = check_approval_timeout()
        assert counts["escalated"] == 1
        req.refresh_from_db()
        assert req.status == "pending" and req.current_level == 2

    def test_fresh_request_untouched(self, ws, requester, approver_a, make_process, record_id):
        process = make_process([_level(approver_a.id, on_timeout="auto_reject")])
        req = ApprovalService.create_request(
            process_id=process.id, record_id=record_id, requested_by=requester.id,
            workspace_id=ws.id)
        check_approval_timeout()
        req.refresh_from_db()
        assert req.status == "pending"
