"""
Project Management + PSA (Phase P2.10) — native engine validation (scheduling/critical-path,
resource/capacity, budget/profitability/EVM, cost rollup), lifecycle + audit, framework install,
and cross-module cost integration. Covers spec Modules 43/45/48/49/50/52/55.
"""
import uuid

import pytest

from apps.eventstore.models import DomainEvent
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.projects import financials, resources, scheduling
from apps.projects.blueprint import build_projects_manifest, seed_projects_template
from apps.projects.models import ProjectCostEntry
from apps.projects.scheduling import SchedulingError
from apps.projects.services import (
    CostRollupService,
    FinancialsService,
    ProjectService,
    ResourceService,
    SchedulingService,
)
from apps.reporting.models import Dashboard
from apps.solution_templates import services as st
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.workflows.models import WorkflowDefinition

A = str(uuid.uuid4())


# ── Module 50: scheduling / critical path (pure) ─────────────────────────────
def test_critical_path_linear_chain():
    tasks = [{"id": "a", "duration": 3}, {"id": "b", "duration": 2}, {"id": "c", "duration": 4}]
    deps = [{"predecessor": "a", "successor": "b"}, {"predecessor": "b", "successor": "c"}]
    cp = scheduling.critical_path(tasks, deps)
    assert cp["project_duration"] == 9
    assert set(cp["critical_task_ids"]) == {"a", "b", "c"}


def test_critical_path_float_on_parallel_branch():
    # a→c (a=2,c=2) and a→b→c (b=1) ; b has float.
    tasks = [{"id": "a", "duration": 2}, {"id": "b", "duration": 1}, {"id": "c", "duration": 2}]
    deps = [{"predecessor": "a", "successor": "b"}, {"predecessor": "a", "successor": "c"},
            {"predecessor": "b", "successor": "c"}]
    cp = scheduling.critical_path(tasks, deps)
    assert cp["total_float"]["b"] == 0  # b is on the longest path a→b→c (5) > a→c
    assert cp["project_duration"] == 5


def test_critical_path_detects_cycle():
    tasks = [{"id": "a", "duration": 1}, {"id": "b", "duration": 1}]
    deps = [{"predecessor": "a", "successor": "b"}, {"predecessor": "b", "successor": "a"}]
    with pytest.raises(SchedulingError):
        scheduling.critical_path(tasks, deps)


# ── Module 48: resources / capacity (pure) ───────────────────────────────────
def test_utilization_over_allocation_and_conflict():
    allocs = [{"employee": "e1", "allocation_percent": 70, "project": "p1"},
              {"employee": "e1", "allocation_percent": 50, "project": "p2"},
              {"employee": "e2", "allocation_percent": 40, "project": "p1"}]
    u = resources.utilization(allocs)
    e1 = next(r for r in u["utilization"] if r["employee"] == "e1")
    assert e1["total_percent"] == 120.0 and e1["over_allocated"]
    assert len(u["conflicts"]) == 1
    e2 = next(r for r in u["utilization"] if r["employee"] == "e2")
    assert e2["under_allocated"] and e2["available_percent"] == 60.0


def test_capacity_hours():
    allocs = [{"employee": "e1", "allocation_percent": 50}]
    cap = resources.capacity(allocs, weekly_hours=40)["capacity"][0]
    assert cap["allocated_hours"] == 20.0 and cap["available_hours"] == 20.0


# ── Module 49: financials / EVM (pure) ───────────────────────────────────────
def test_budget_and_profitability():
    b = financials.budget_status(planned_budget=10000, actual_cost=4000, forecast_cost=11000)
    assert b["remaining_budget"] == "6000.00" and b["over_budget"] is False
    assert b["budget_variance"] == "-1000.00"  # planned - forecast
    p = financials.profitability(revenue=12000, cost=4000)
    assert p["profit"] == "8000.00" and p["margin_percent"] == pytest.approx(66.67, abs=0.01)


def test_earned_value():
    ev = financials.earned_value(planned_value=10000, earned_value=5000, actual_cost=4000,
                                 budget_at_completion=10000)
    assert ev["cost_variance"] == "1000.00"      # EV - AC
    assert ev["schedule_variance"] == "-5000.00"  # EV - PV
    assert ev["cpi"] == pytest.approx(1.25, abs=0.01)
    assert ev["spi"] == pytest.approx(0.5, abs=0.01)


def test_cost_rollup_by_source():
    r = financials.cost_rollup([{"source": "payroll", "amount": 1000},
                                {"source": "procurement", "amount": 500},
                                {"source": "payroll", "amount": 250}])
    assert r["total_cost"] == "1750.00" and r["by_source"]["payroll"] == "1250.00"


# ── framework provisioning ────────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_projects_manifest()) == []


@pytest.fixture
def installed_ws(db):
    ws = uuid.uuid4()
    st.install(template_id=seed_projects_template().id, workspace_id=ws, installed_by=None)
    return ws


@pytest.mark.django_db
def test_install_provisions_psa_solution():
    ws = uuid.uuid4()
    st.install(template_id=seed_projects_template().id, workspace_id=ws, installed_by=None)
    for slug in ["portfolio", "program", "project", "task", "milestone", "timesheet",
                 "risk", "issue", "change_request", "sprint"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="timesheet_approval").exists()
    assert Role.objects.filter(workspace_id=ws, slug="pmo_manager").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 3
    assert Application.objects.filter(workspace_id=ws, slug="projects").exists()


# ── Module 43/52: lifecycle + audit ──────────────────────────────────────────
@pytest.mark.django_db
def test_project_and_task_lifecycle_audit(installed_ws):
    ws = installed_ws
    proj = ProjectService.create_document(
        workspace_id=ws, entity_slug="project",
        data={"name": "Apollo", "status": "draft", "planned_budget": "10000"}, actor_id=A)
    assert proj["number"] == "PRJ-000001"
    ProjectService.start_project(workspace_id=ws, record_id=proj["id"], actor_id=A)
    task = ProjectService.create_document(
        workspace_id=ws, entity_slug="task",
        data={"project": proj["id"], "title": "Build", "status": "in_progress"}, actor_id=A)
    assert task["number"] == "TSK-000001"
    ProjectService.complete_task(workspace_id=ws, record_id=task["id"], actor_id=A)
    ProjectService.approve_budget(workspace_id=ws, record_id=proj["id"], actor_id=A)
    ProjectService.complete_project(workspace_id=ws, record_id=proj["id"], actor_id=A)
    for ev in ["project.created", "project.started", "task.created", "task.completed",
               "budget.approved", "project.completed"]:
        assert DomainEvent.objects.filter(event_type=ev).exists(), ev


# ── Module 20/49: cost rollup (cross-module integration) + financials ────────
@pytest.mark.django_db
def test_cost_rollup_and_financials(installed_ws):
    ws = installed_ws
    proj = ProjectService.create_document(
        workspace_id=ws, entity_slug="project",
        data={"name": "Beta", "status": "active", "planned_budget": "10000",
              "revenue": "12000"}, actor_id=A)
    pid = proj["id"]
    # Costs from multiple modules + an approved timesheet (labour).
    CostRollupService.post_cost(workspace_id=ws, project_record_id=pid, source="payroll",
                                amount=1000, actor_id=A)
    CostRollupService.post_cost(workspace_id=ws, project_record_id=pid, source="procurement",
                                amount=500, actor_id=A)
    ProjectService.create_document(
        workspace_id=ws, entity_slug="timesheet",
        data={"project": pid, "hours": "10", "rate": "50", "status": "approved"}, actor_id=A)

    roll = CostRollupService.rollup_project(workspace_id=ws, project_record_id=pid)
    assert roll["total_cost"] == "2000.00"          # 1000 + 500 + (10*50)
    assert roll["by_source"]["timesheet"] == "500.00"
    assert ProjectCostEntry.objects.filter(workspace_id=ws, project_record_id=pid).count() == 2

    # 2 of 4 tasks complete → 50% progress, EV = 5000.
    for i in range(4):
        t = ProjectService.create_document(
            workspace_id=ws, entity_slug="task",
            data={"project": pid, "title": f"T{i}", "status": "backlog"}, actor_id=A)
        if i < 2:
            ProjectService.complete_task(workspace_id=ws, record_id=t["id"], actor_id=A)

    fin = FinancialsService.project_financials(workspace_id=ws, project_record_id=pid)
    assert fin["budget"]["actual_cost"] == "2000.00"
    assert fin["budget"]["remaining_budget"] == "8000.00"
    assert fin["progress_percent"] == 50.0
    assert fin["earned_value"]["earned_value"] == "5000.00"
    assert fin["profitability"]["profit"] == "10000.00"   # 12000 - 2000


# ── Module 48/50: native engine reads over metadata ──────────────────────────
@pytest.mark.django_db
def test_schedule_and_utilization_from_metadata(installed_ws):
    ws = installed_ws
    proj = ProjectService.create_document(
        workspace_id=ws, entity_slug="project", data={"name": "Gamma"}, actor_id=A)
    pid = proj["id"]
    t1 = ProjectService.create_document(
        workspace_id=ws, entity_slug="task",
        data={"project": pid, "title": "A", "planned_hours": "16"}, actor_id=A)  # 2 days
    t2 = ProjectService.create_document(
        workspace_id=ws, entity_slug="task",
        data={"project": pid, "title": "B", "planned_hours": "8"}, actor_id=A)   # 1 day
    ProjectService.create_document(
        workspace_id=ws, entity_slug="task_dependency",
        data={"project": pid, "predecessor_task": t1["id"], "successor_task": t2["id"],
              "dependency_type": "finish_to_start"}, actor_id=A)
    sched = SchedulingService.project_schedule(workspace_id=ws, project_record_id=pid)
    assert sched["project_duration"] == 3  # 2 + 1
    assert str(t1["id"]) in sched["critical_task_ids"]

    ProjectService.create_document(
        workspace_id=ws, entity_slug="project_member",
        data={"project": pid, "employee": A, "allocation_percent": "120"}, actor_id=A)
    util = ResourceService.workspace_utilization(workspace_id=ws)
    assert len(util["conflicts"]) == 1  # the 120% allocation
