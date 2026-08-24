"""
Workflow ``action_guard`` executor (Platform Gap A, first consumer) — proves record-parameterized
cross-record validation: ``{{record.*}}`` templates in the guard query resolve against the trigger
record (reusing resolve_value), the domain-agnostic GuardService measures it, and the step branches
true/false so workflow edges route confirm/reject.
"""
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member
from apps.workflows.executors import get_executor


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=w, slug="booking", name="Booking",
                                        plural_name="Bookings")
    for slug in ("item", "status"):
        SchemaRegistryService.add_field(workspace_id=w, entity_slug="booking", slug=slug,
                                        name=slug.title(), field_type="text", is_promoted=True)
    return w


def _confirm(ws, item, n):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="booking")
    for _ in range(n):
        RecordService.create_record(workspace_id=ws, member=system_member(None), entity=entity,
                                    data={"item": item, "status": "confirmed"})


def _run(ws):
    class _Run:
        id = uuid.uuid4()
        workspace_id = ws
        initiated_by = None
        record_id = None
        entity_id = None
        context: dict = {}
    return _Run()


def _guard_step():
    class _Step:
        id = uuid.uuid4()
        config = {"guards": [{
            "name": "capacity",
            "query": {"entity": "booking", "filter": {"op": "and", "conditions": [
                {"field": "item", "op": "=", "value": "{{record.item}}"},
                {"field": "status", "op": "=", "value": "confirmed"}]}},
            "aggregate": "count", "operator": "lt", "threshold": 2, "message": "full"}]}
    return _Step()


@pytest.mark.django_db
def test_guard_branches_true_when_capacity_ok(ws):
    _confirm(ws, "A", 1)
    out = get_executor("action_guard")(_guard_step(), _run(ws), {"record": {"item": "A"}}, None)
    assert out["branch"] == "true" and out["passed"] is True   # 1 < 2 → record-parameterized query worked


@pytest.mark.django_db
def test_guard_branches_false_when_full(ws):
    _confirm(ws, "A", 2)
    out = get_executor("action_guard")(_guard_step(), _run(ws), {"record": {"item": "A"}}, None)
    assert out["branch"] == "false" and out["passed"] is False
    assert out["failures"][0]["name"] == "capacity"


@pytest.mark.django_db
def test_guard_scopes_to_the_trigger_record(ws):
    """Filling item A must NOT block a registration for item B — the template scopes per record."""
    _confirm(ws, "A", 5)
    out = get_executor("action_guard")(_guard_step(), _run(ws), {"record": {"item": "B"}}, None)
    assert out["branch"] == "true"   # B has 0 confirmed → passes


@pytest.mark.django_db
def test_guard_branch_routes_only_the_matching_edge(ws):
    """Engine-level routing regression: a guard step's true/false branch must route to ONLY the
    matching-label edge (like ``condition``). Before the Gap-A routing fix the engine honoured
    ``branch`` for ``condition`` steps only, so a guard fired BOTH edges (the false path always ran).
    """
    from apps.workflows.models import WorkflowDefinition, WorkflowEdge, WorkflowStep
    from apps.workflows.services import WorkflowService

    wf = WorkflowDefinition.objects.create(
        workspace_id=ws, name="Guard Route", slug="guard_route",
        trigger_type="record_created", status="active")
    guard = WorkflowStep.objects.create(workflow_id=wf.id, workspace_id=ws,
                                        step_type="action_guard", name="Guard", is_entry=True)
    ok = WorkflowStep.objects.create(workflow_id=wf.id, workspace_id=ws,
                                     step_type="action_send_notification", name="OK")
    reject = WorkflowStep.objects.create(workflow_id=wf.id, workspace_id=ws,
                                         step_type="action_update_record", name="Reject")
    WorkflowEdge.objects.create(workflow_id=wf.id, workspace_id=ws, source_step_id=guard.id,
                                target_step_id=ok.id, condition_label="true")
    WorkflowEdge.objects.create(workflow_id=wf.id, workspace_id=ws, source_step_id=guard.id,
                                target_step_id=reject.id, condition_label="false")
    run = _run(ws)
    assert WorkflowService._next_step_ids(run, guard, {"branch": "true"}) == [ok.id]
    assert WorkflowService._next_step_ids(run, guard, {"branch": "false"}) == [reject.id]
