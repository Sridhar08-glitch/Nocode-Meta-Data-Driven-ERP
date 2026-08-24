"""
Project Management services (Phase P2.10).

``ProjectService`` is the thin lifecycle over the framework metadata entities (numbering + audit
via the reusable ``SolutionDocumentService``). ``CostRollupService`` (native) aggregates costs
from every source — payroll/procurement/assets/expenses/timesheets — into the project cost ledger
and rolls them onto the project (the cross-module integration point). ``FinancialsService``,
``ResourceService`` and ``SchedulingService`` read metadata in bulk (no per-record N+1) and run the
pure engines. GL posting is decoupled via GLBus (a missing chart never blocks the operation).
"""
from __future__ import annotations

import contextlib
import uuid
from decimal import Decimal

from apps.ledger.provisioning import ensure_accounting_settings
from apps.records.services import RecordService, resolve_entity
from apps.solution_templates.documents import (
    SolutionDocumentService as Docs,
)
from apps.solution_templates.documents import (
    emit_event,
    system_member,
)

from . import financials, resources, scheduling
from .blueprint import EVENT_KEY, PROJECT_SEQUENCES
from .financials import money
from .models import ProjectBaseline, ProjectCostEntry


class ProjectError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _list(workspace_id, slug, filter_source=None, member=None, limit=5000):
    member = member or system_member(None)
    try:
        entity = resolve_entity(workspace_id, slug)
    except Exception:  # noqa: BLE001 — entity not installed
        return []
    return RecordService.list_records(
        workspace_id=workspace_id, member=member, entity=entity,
        filter_source=filter_source, limit=limit)


def _by_project(slug, project_record_id):
    return {"field": "project", "op": "=", "value": str(project_record_id)}


# ── lifecycle (framework metadata) ───────────────────────────────────────────
class ProjectService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        for key, defaults in PROJECT_SEQUENCES.items():
            NumberingService.ensure_sequence(
                workspace_id, key, defaults=defaults, created_by=actor_id)

    @staticmethod
    def create_document(*, workspace_id, entity_slug, data, member=None, actor_id=None):
        event = (f"{EVENT_KEY[entity_slug]}.created" if entity_slug in EVENT_KEY else None)
        return Docs.create(
            workspace_id=workspace_id, entity_slug=entity_slug, data=data, member=member,
            actor_id=actor_id,
            sequence_key=entity_slug if entity_slug in PROJECT_SEQUENCES else None,
            sequence_defaults=PROJECT_SEQUENCES.get(entity_slug), event_type=event)

    @staticmethod
    def _transition(workspace_id, slug, record_id, updates, event, member, actor_id,
                    payload=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug=slug, record_id=record_id, updates=updates,
            member=member, actor_id=actor_id, event_type=event, event_payload=payload)

    @staticmethod
    def start_project(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "project", record_id,
                                          {"status": "active"}, "project.started",
                                          member, actor_id)

    @staticmethod
    def complete_project(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "project", record_id,
                                          {"status": "completed"}, "project.completed",
                                          member, actor_id)

    @staticmethod
    def complete_task(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "task", record_id,
                                          {"status": "completed"}, "task.completed",
                                          member, actor_id)

    @staticmethod
    def complete_milestone(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "milestone", record_id,
                                          {"status": "completed"}, "milestone.completed",
                                          member, actor_id)

    @staticmethod
    def approve_timesheet(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "timesheet", record_id,
                                          {"status": "approved"}, "timesheet.approved",
                                          member, actor_id)

    @staticmethod
    def approve_expense(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "expense", record_id,
                                          {"status": "approved"}, "expense.approved",
                                          member, actor_id)

    @staticmethod
    def approve_change_request(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "change_request", record_id,
                                          {"status": "approved"}, "change_request.approved",
                                          member, actor_id)

    @staticmethod
    def approve_deliverable(*, workspace_id, record_id, member=None, actor_id=None):
        return ProjectService._transition(workspace_id, "deliverable", record_id,
                                          {"acceptance_status": "accepted"},
                                          "deliverable.approved", member, actor_id)

    @staticmethod
    def approve_budget(*, workspace_id, record_id, member=None, actor_id=None):
        """Approve a project's budget (audit hook for the budget-approval workflow)."""
        proj = Docs.retrieve(workspace_id=workspace_id, entity_slug="project",
                             record_id=record_id, member=member, actor_id=actor_id)
        emit_event(workspace_id, "project", record_id, "budget.approved",
                   {"planned_budget": str(proj.get("planned_budget"))}, actor_id)
        return proj

    @staticmethod
    def baseline_project(*, workspace_id, record_id, member=None, actor_id=None):
        proj = Docs.retrieve(workspace_id=workspace_id, entity_slug="project",
                             record_id=record_id, member=member, actor_id=actor_id)
        return ProjectBaseline.objects.create(
            workspace_id=workspace_id, project_record_id=record_id,
            planned_budget=money(proj.get("planned_budget")),
            snapshot={"name": proj.get("name"), "planned_budget": str(proj.get("planned_budget")),
                      "end_date": proj.get("end_date")}, created_by=_uid(actor_id))


# ── cost rollup (native, cross-module integration) ───────────────────────────
class CostRollupService:
    @staticmethod
    def post_cost(*, workspace_id, project_record_id, source, amount, description="",
                  entry_date=None, reference="", post_gl=False, actor_id=None) -> ProjectCostEntry:
        """Record a project cost from any source (payroll/procurement/asset/expense/timesheet).
        Optionally posts a WIP GL entry.

        Idempotent on ``reference`` (Blocker 5): when a posting reference is supplied, a retry /
        queue replay / double-click for the same (project, source, reference) returns the existing
        cost entry instead of inflating ``actual_cost`` with a duplicate. References are how every
        cross-module poster (payroll run id, vendor bill number, …) identifies its cost line."""
        defaults = {"description": description, "amount": money(amount),
                    "entry_date": entry_date, "created_by": _uid(actor_id)}
        if reference:
            entry, created = ProjectCostEntry.objects.get_or_create(
                workspace_id=workspace_id, project_record_id=project_record_id,
                source=source, reference=reference, defaults=defaults)
            if not created:
                return entry  # idempotent: this cost was already posted
        else:
            entry = ProjectCostEntry.objects.create(
                workspace_id=workspace_id, project_record_id=project_record_id, source=source,
                reference=reference, **defaults)
        if post_gl and money(amount) > 0 and entry_date is not None:
            entry.journal_entry_id = CostRollupService._post_gl(
                workspace_id, entry, actor_id)
            entry.save(update_fields=["journal_entry_id"])
        return entry

    @staticmethod
    def _post_gl(workspace_id, entry, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        s = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        try:
            je = GLBus.post(
                workspace_id, date=entry.entry_date, lines=[
                    {"account_code": s.default_wip_account, "debit": str(entry.amount),
                     "memo": "Project WIP"},
                    {"account_code": "2300", "credit": str(entry.amount),
                     "memo": "Cost accrual"}],
                memo="Project cost", source_module="projects",
                source_ref=str(entry.project_record_id), actor_id=actor_id)
            return je.id if je is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="projects",
                              source_ref=str(entry.project_record_id),
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def rollup_project(*, workspace_id, project_record_id, member=None, actor_id=None) -> dict:
        """Aggregate the project cost ledger + labour from approved timesheets, then write
        ``actual_cost`` back onto the project metadata. Batch-read (no N+1)."""
        entries = list(ProjectCostEntry.objects.filter(
            workspace_id=workspace_id, project_record_id=project_record_id).values(
            "source", "amount"))
        rows = [{"source": e["source"], "amount": e["amount"]} for e in entries]
        # Labour cost = Σ approved timesheet hours × rate (read metadata in bulk).
        labour = Decimal("0.00")
        for ts in _list(workspace_id, "timesheet", _by_project("timesheet", project_record_id),
                       member):
            if ts.get("status") == "approved":
                labour += money(ts.get("hours")) * money(ts.get("rate"))
        if labour > 0:
            rows.append({"source": "timesheet", "amount": labour})
        roll = financials.cost_rollup(rows)
        with contextlib.suppress(Exception):
            entity = resolve_entity(workspace_id, "project")
            RecordService.update_record(
                workspace_id=workspace_id, member=member or system_member(actor_id),
                entity=entity, record_id=project_record_id,
                data={"actual_cost": roll["total_cost"]})
        return roll


# ── financials / EVM (native) ────────────────────────────────────────────────
class FinancialsService:
    @staticmethod
    def project_financials(*, workspace_id, project_record_id, member=None) -> dict:
        proj = Docs.retrieve(workspace_id=workspace_id, entity_slug="project",
                             record_id=project_record_id, member=member)
        tasks = _list(workspace_id, "task", _by_project("task", project_record_id), member)
        total = len(tasks) or 1
        done = sum(1 for t in tasks if t.get("status") == "completed")
        progress = Decimal(done) / Decimal(total)
        planned = money(proj.get("planned_budget"))
        actual = money(proj.get("actual_cost"))
        revenue = money(proj.get("revenue"))
        # PV ≈ full planned budget (plan complete); EV = planned × % work complete.
        pv = planned
        ev = money(planned * progress)
        return {
            "budget": financials.budget_status(
                planned_budget=planned, actual_cost=actual,
                forecast_cost=proj.get("forecast_cost")),
            "profitability": financials.profitability(revenue=revenue, cost=actual),
            "earned_value": financials.earned_value(
                planned_value=pv, earned_value=ev, actual_cost=actual,
                budget_at_completion=planned),
            "progress_percent": float(money(progress * 100)),
            "task_count": len(tasks), "completed_tasks": done,
        }


# ── resources + capacity (native) ────────────────────────────────────────────
class ResourceService:
    @staticmethod
    def workspace_utilization(*, workspace_id, member=None) -> dict:
        members = _list(workspace_id, "project_member", None, member)
        allocs = [{"employee": m.get("employee"), "project": m.get("project"),
                   "allocation_percent": m.get("allocation_percent")} for m in members]
        return resources.utilization(allocs)

    @staticmethod
    def workspace_capacity(*, workspace_id, weekly_hours=40.0, member=None) -> dict:
        members = _list(workspace_id, "project_member", None, member)
        allocs = [{"employee": m.get("employee"),
                   "allocation_percent": m.get("allocation_percent")} for m in members]
        return resources.capacity(allocs, weekly_hours=weekly_hours)


# ── scheduling / critical path (native) ──────────────────────────────────────
class SchedulingService:
    @staticmethod
    def project_schedule(*, workspace_id, project_record_id, member=None) -> dict:
        tasks_raw = _list(workspace_id, "task", _by_project("task", project_record_id), member)
        deps_raw = _list(workspace_id, "task_dependency",
                        _by_project("task_dependency", project_record_id), member)
        tasks = [{"id": str(t["id"]), "duration": _duration(t)} for t in tasks_raw]
        deps = [{"predecessor": str(d.get("predecessor_task")),
                 "successor": str(d.get("successor_task")),
                 "dependency_type": d.get("dependency_type", "finish_to_start"),
                 "lag_days": d.get("lag_days", 0)}
                for d in deps_raw if d.get("predecessor_task") and d.get("successor_task")]
        cp = scheduling.critical_path(tasks, deps)
        cp["gantt"] = scheduling.gantt_bars(tasks, deps)
        return cp


def _duration(task: dict) -> float:
    """Task duration in days from start/due dates, else planned_hours/8, else 1."""
    start, due = task.get("start_date"), task.get("due_date")
    if start and due:
        from datetime import date

        def _d(v):
            return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
        with contextlib.suppress(Exception):
            return max((_d(due) - _d(start)).days, 0) + 1
    ph = task.get("planned_hours")
    if ph:
        return max(float(ph) / 8.0, 0)
    return 1.0
