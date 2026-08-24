"""
Workflow ``action_aggregate`` executor (Platform Gap CG-2, first consumer) — proves
record-parameterized cross-record aggregation + calculation + PERSISTENCE: ``{{record.*}}`` in the
measure query resolves against the trigger record (reusing resolve_value), the domain-agnostic
AggregationService computes a weighted value, and the executor writes it back to a target record via
RecordService and injects the outputs into the run context. Generic entities — no domain logic.
"""
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member
from apps.workflows.executors import get_executor, member_for_run


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    # parent `basket` with a persisted total field; child `line` with a formula amount = qty*price.
    SchemaRegistryService.create_entity(workspace_id=w, slug="basket", name="Basket",
                                        plural_name="Baskets")
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="basket", slug="total", name="Total",
                                    field_type="decimal", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="basket", slug="line_count",
                                    name="Line Count", field_type="integer", is_promoted=True)
    SchemaRegistryService.create_entity(workspace_id=w, slug="line", name="Line",
                                        plural_name="Lines")
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug="basket", name="Basket",
                                    field_type="text", is_promoted=True)
    for slug in ("qty", "price"):
        SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug=slug,
                                        name=slug.title(), field_type="integer", is_promoted=True)
    # NOT promoted (formula column is JSONB on PG); custom_data + NQL ::numeric cast → SQL-summable.
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug="amount", name="Amount",
                                    field_type="formula", is_promoted=False,
                                    config={"expression": "qty * price"})
    return w


def _mk(ws, slug, data):
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=system_member(None), entity=entity,
                                       data=data)


def _run(ws):
    class _Run:
        id = uuid.uuid4()
        workspace_id = ws
        initiated_by = None
        record_id = None
        entity_id = None
        context: dict = {}
    return _Run()


def _agg_step(basket_id):
    class _Step:
        id = uuid.uuid4()
        config = {
            "measures": [
                {"name": "total", "aggregate": "sum", "field": "amount",
                 "query": {"entity": "line", "filter": {"op": "and", "conditions": [
                     {"field": "basket", "op": "=", "value": "{{record.id}}"}]}}},
                {"name": "n", "aggregate": "count",
                 "query": {"entity": "line", "filter": {"op": "and", "conditions": [
                     {"field": "basket", "op": "=", "value": "{{record.id}}"}]}}},
            ],
            "computes": [{"name": "avg", "expression": "total / n if n > 0 else 0"}],
            "target": {"entity_slug": "basket", "record_id": "{{record.id}}",
                       "data": {"total": "{{agg.total}}", "line_count": "{{agg.n}}"}},
        }
    return _Step()


@pytest.mark.django_db
def test_aggregate_computes_and_persists_to_target(ws):
    basket = _mk(ws, "basket", {"total": 0, "line_count": 0})
    bid = str(basket["id"])
    for qty, price in [(2, 5), (3, 5), (1, 10)]:          # amounts 10, 15, 10 → total 35, n 3
        _mk(ws, "line", {"basket": bid, "qty": qty, "price": price})

    run = _run(ws)
    out = get_executor("action_aggregate")(_agg_step(bid), run, {"record": {"id": bid}},
                                            member_for_run(run))

    assert out["persisted"] is True and not out["errors"]
    assert out["outputs"]["total"] == 35 and out["outputs"]["n"] == 3
    assert float(out["outputs"]["avg"]) == pytest.approx(35 / 3)
    # persisted to the target record via RecordService
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="basket")
    refreshed = RecordService.retrieve_record(workspace_id=ws, member=system_member(None),
                                               entity=entity, record_id=basket["id"])
    assert float(refreshed["total"]) == 35 and int(refreshed["line_count"]) == 3


@pytest.mark.django_db
def test_aggregate_scopes_to_the_trigger_record(ws):
    """Lines under basket A must NOT count toward basket B — the template scopes per record."""
    a = _mk(ws, "basket", {"total": 0, "line_count": 0})
    b = _mk(ws, "basket", {"total": 0, "line_count": 0})
    for _ in range(3):
        _mk(ws, "line", {"basket": str(a["id"]), "qty": 1, "price": 1})
    run = _run(ws)
    out = get_executor("action_aggregate")(_agg_step(str(b["id"])), run,
                                            {"record": {"id": str(b["id"])}}, member_for_run(run))
    assert out["outputs"]["n"] == 0 and out["outputs"]["total"] == 0


@pytest.mark.django_db
def test_aggregate_without_target_only_injects_outputs(ws):
    basket = _mk(ws, "basket", {"total": 0, "line_count": 0})
    _mk(ws, "line", {"basket": str(basket["id"]), "qty": 4, "price": 5})

    class _Step:
        id = uuid.uuid4()
        config = {"into": "roll", "measures": [
            {"name": "total", "aggregate": "sum", "field": "amount",
             "query": {"entity": "line", "filter": {"op": "and", "conditions": [
                 {"field": "basket", "op": "=", "value": "{{record.id}}"}]}}}]}

    ctx = {"record": {"id": str(basket["id"])}}
    out = get_executor("aggregate")(_Step(), _run(ws), ctx, None)
    assert out["persisted"] is False and out["outputs"]["total"] == 20
    assert ctx["roll"]["total"] == 20                     # injected under the configured key
