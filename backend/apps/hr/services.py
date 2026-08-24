"""
HR native services (Phase P2.7) — a THIN lifecycle layer.

Almost the entire HR solution is provisioned by the framework (``blueprint.py``). The only
native code is the employee-lifecycle integrity (candidate→employee, leave approval with a
balance calculation, promotion/transfer/offboarding) — and it delegates numbering + audit to
the reusable ``SolutionDocumentService``. This keeps HR well under the <10%-native target.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from apps.solution_templates.documents import SolutionDocumentService as Docs

from .blueprint import EVENT_KEY, HR_SEQUENCES


class HRError(Exception):  # noqa: N818 — domain error
    pass


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class HRService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        for key, defaults in HR_SEQUENCES.items():
            NumberingService.ensure_sequence(
                workspace_id, key, defaults=defaults, created_by=actor_id)

    @staticmethod
    def create_document(*, workspace_id, entity_slug, data, member=None, actor_id=None):
        """Create an HR record; candidate/interview/offer/employee get a gapless number."""
        event = (f"hr.{EVENT_KEY[entity_slug]}.created"
                 if entity_slug in EVENT_KEY else None)
        return Docs.create(
            workspace_id=workspace_id, entity_slug=entity_slug, data=data,
            member=member, actor_id=actor_id,
            sequence_key=entity_slug if entity_slug in HR_SEQUENCES else None,
            sequence_defaults=HR_SEQUENCES.get(entity_slug), event_type=event)

    # ── recruitment lifecycle ─────────────────────────────────────────────────
    @staticmethod
    def complete_interview(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="interview", record_id=record_id,
            updates={"status": "completed"}, member=member, actor_id=actor_id,
            event_type="hr.interview.completed")

    @staticmethod
    def accept_offer(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="offer", record_id=record_id,
            updates={"status": "accepted"}, member=member, actor_id=actor_id,
            event_type="hr.offer.accepted")

    @staticmethod
    def hire_candidate(*, workspace_id, record_id, member=None, actor_id=None):
        """Mark a candidate Hired and create the Employee record (EMP-numbered) — the
        Candidate→Employee step of the lifecycle."""
        cand = Docs.transition(
            workspace_id=workspace_id, entity_slug="candidate", record_id=record_id,
            updates={"status": "hired"}, member=member, actor_id=actor_id)
        emp = HRService.create_document(
            workspace_id=workspace_id, entity_slug="employee",
            data={"first_name": cand.get("first_name"), "last_name": cand.get("last_name"),
                  "email": cand.get("email"), "phone": cand.get("phone"),
                  "status": "probation", "employment_type": "permanent"},
            member=member, actor_id=actor_id)
        return {"candidate": cand, "employee": emp}

    # ── leave (native balance calculation) ────────────────────────────────────
    @staticmethod
    def approve_leave(*, workspace_id, record_id, member=None, actor_id=None):
        """Approve a leave request and decrement the linked leave balance (used += days,
        remaining = allocated - used). The balance maths is the genuine native HR logic."""
        req = Docs.transition(
            workspace_id=workspace_id, entity_slug="leave_request", record_id=record_id,
            updates={"status": "approved"}, member=member, actor_id=actor_id,
            event_type="hr.leave.approved")
        balance_id = req.get("leave_balance")
        days = _dec(req.get("days"))
        if balance_id and days and days > 0:
            try:
                bal = Docs.retrieve(workspace_id=workspace_id, entity_slug="leave_balance",
                                    record_id=balance_id, member=member, actor_id=actor_id)
                allocated = _dec(bal.get("allocated")) or Decimal("0")
                used = (_dec(bal.get("used")) or Decimal("0")) + days
                Docs.transition(
                    workspace_id=workspace_id, entity_slug="leave_balance",
                    record_id=balance_id,
                    updates={"used": str(used), "remaining": str(allocated - used)},
                    member=member, actor_id=actor_id)
            except Exception:  # noqa: BLE001 — balance update is best-effort, never blocks approval
                pass
        return req

    @staticmethod
    def reject_leave(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="leave_request", record_id=record_id,
            updates={"status": "rejected"}, member=member, actor_id=actor_id,
            event_type="hr.leave.rejected")

    # ── performance ───────────────────────────────────────────────────────────
    @staticmethod
    def complete_performance(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="performance_review", record_id=record_id,
            updates={"status": "completed"}, member=member, actor_id=actor_id,
            event_type="hr.performance.completed")

    # ── promotion / transfer / offboarding ────────────────────────────────────
    @staticmethod
    def promote_employee(*, workspace_id, record_id, new_position, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="employee", record_id=record_id,
            updates={"position": new_position}, member=member, actor_id=actor_id,
            event_type="hr.employee.promoted", event_payload={"new_position": new_position})

    @staticmethod
    def transfer_employee(*, workspace_id, record_id, new_department, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="employee", record_id=record_id,
            updates={"department": new_department}, member=member, actor_id=actor_id,
            event_type="hr.employee.transferred",
            event_payload={"new_department": new_department})

    @staticmethod
    def offboard_employee(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="employee", record_id=record_id,
            updates={"status": "terminated"}, member=member, actor_id=actor_id,
            event_type="hr.employee.offboarded")
