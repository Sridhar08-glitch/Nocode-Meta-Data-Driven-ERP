"""
Aggregation Framework (Platform Gap CG-2) certification — the reusable, domain-agnostic
cross-record aggregation + calculation + persistence capability. Proves every aggregate, the
**weighted pattern** (per-child product via a formula field + parent SUM — the generic mechanism a
weighted average, a cost roll-up, a blended rate, etc. all reduce to), multi-measure + derived
compute (ratio with zero-guard), structured fail-closed errors, workspace isolation, audit events,
and metrics — over GENERIC entities (nothing domain/package-specific). SQLite + PostgreSQL.
"""
import uuid

import pytest

from apps.aggregation.services import AggregationService
from apps.eventstore.models import DomainEvent
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member


@pytest.fixture
def ws(db):
    """A workspace with a parent `container` + child `line` (qty, price, formula amount=qty*price)."""
    w = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=w, slug="container", name="Container",
                                        plural_name="Containers")
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="container", slug="name",
                                    name="Name", field_type="text", is_promoted=True)
    SchemaRegistryService.create_entity(workspace_id=w, slug="line", name="Line",
                                        plural_name="Lines")
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug="container",
                                    name="Container", field_type="text", is_promoted=True)
    for slug in ("qty", "price"):
        SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug=slug,
                                        name=slug.title(), field_type="integer", is_promoted=True)
    # A per-child formula field (single-record, write-path-wired) — the "weight" building block.
    # NOT promoted: a formula column is JSONB on PG; kept in custom_data, NQL casts it ::numeric so
    # it is SQL-summable on both backends (the correct pattern for a computed field a consumer sums).
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="line", slug="amount", name="Amount",
                                    field_type="formula", is_promoted=False,
                                    config={"expression": "qty * price"})
    return w


def _line(ws, container, qty, price):
    from apps.metadata.models import EntityDefinition
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="line")
    return RecordService.create_record(workspace_id=ws, member=system_member(None), entity=entity,
                                       data={"container": container, "qty": qty, "price": price})


def _q(container):
    return {"entity": "line", "filter": {"op": "and", "conditions": [
        {"field": "container", "op": "=", "value": container}]}}


# ── aggregates ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_sum_count_avg_min_max(ws):
    for qty, price in [(2, 5), (3, 5), (1, 10)]:      # amounts: 10, 15, 10
        _line(ws, "A", qty, price)
    m = [
        {"name": "total", "query": _q("A"), "aggregate": "sum", "field": "amount"},
        {"name": "n", "query": _q("A"), "aggregate": "count"},
        {"name": "avg_amt", "query": _q("A"), "aggregate": "avg", "field": "amount"},
        {"name": "lo", "query": _q("A"), "aggregate": "min", "field": "amount"},
        {"name": "hi", "query": _q("A"), "aggregate": "max", "field": "amount"},
    ]
    r = AggregationService.compute(workspace_id=ws, measures=m, emit=False)
    assert r.values["total"] == 35 and r.values["n"] == 3
    assert float(r.values["avg_amt"]) == pytest.approx(35 / 3)
    assert float(r.values["lo"]) == 10 and float(r.values["hi"]) == 15
    assert not r.errors


@pytest.mark.django_db
def test_weighted_average_via_compute(ws):
    """The generic weighted pattern: Σ(child product) / Σ(weight) — computed + returned, no domain."""
    # weight=qty, value=price → weighted avg price = Σ(qty*price)/Σ(qty) = (10+15+10)/(2+3+1)=35/6
    for qty, price in [(2, 5), (3, 5), (1, 10)]:
        _line(ws, "A", qty, price)
    r = AggregationService.compute(
        workspace_id=ws,
        measures=[{"name": "wsum", "query": _q("A"), "aggregate": "sum", "field": "amount"},
                  {"name": "wq", "query": _q("A"), "aggregate": "sum", "field": "qty"}],
        computes=[{"name": "wavg", "expression": "wsum / wq if wq > 0 else 0"}], emit=False)
    assert float(r.outputs["wavg"]) == pytest.approx(35 / 6)


@pytest.mark.django_db
def test_compute_zero_guard_and_empty(ws):
    """No rows → sums are 0; a zero-guarded ratio returns 0 (never divide-by-zero crash)."""
    r = AggregationService.compute(
        workspace_id=ws,
        measures=[{"name": "s", "query": _q("Z"), "aggregate": "sum", "field": "amount"},
                  {"name": "c", "query": _q("Z"), "aggregate": "count"}],
        computes=[{"name": "ratio", "expression": "s / c if c > 0 else 0"}], emit=False)
    assert r.values["s"] == 0 and r.values["c"] == 0 and r.outputs["ratio"] == 0


@pytest.mark.django_db
def test_unguarded_divide_by_zero_is_fail_closed(ws):
    r = AggregationService.compute(
        workspace_id=ws,
        measures=[{"name": "c", "query": _q("Z"), "aggregate": "count"}],
        computes=[{"name": "bad", "expression": "10 / c"}], emit=False)   # c == 0
    assert r.computed["bad"] is None
    assert {e["code"] for e in r.errors} == {"compute_error"}


@pytest.mark.django_db
def test_compute_chain_references_earlier(ws):
    _line(ws, "A", 4, 5)                              # amount 20
    r = AggregationService.compute(
        workspace_id=ws,
        measures=[{"name": "t", "query": _q("A"), "aggregate": "sum", "field": "amount"}],
        computes=[{"name": "half", "expression": "t / 2"},
                  {"name": "quarter", "expression": "half / 2"}], emit=False)
    assert r.outputs["t"] == 20 and r.outputs["half"] == 10 and r.outputs["quarter"] == 5


# ── structured errors (fail-closed), isolation, audit, metrics ────────────────
@pytest.mark.django_db
def test_structured_errors_fail_closed(ws):
    bad = [
        {"name": "agg", "query": _q("A"), "aggregate": "median", "field": "amount"},
        {"name": "noq", "aggregate": "sum", "field": "amount"},
        {"name": "nofield", "query": _q("A"), "aggregate": "sum"},
        {"name": "badent", "query": {"entity": "nope", "filter": {"op": "and", "conditions": []}},
         "aggregate": "count"},
    ]
    r = AggregationService.compute(workspace_id=ws, measures=bad,
                                   computes=[{"name": "x"}], emit=False)   # invalid compute (no expr)
    codes = {e["code"] for e in r.errors}
    assert codes == {"invalid_aggregate", "invalid_measure", "nql_error", "invalid_compute"}
    assert r.values["agg"] is None and r.values["noq"] is None      # fail-closed
    # no stack traces leaked
    assert all(set(e) == {"name", "code", "message"} for e in r.errors)


@pytest.mark.django_db
def test_workspace_isolation(ws):
    _line(ws, "A", 2, 5)
    other = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=other, slug="line", name="Line",
                                        plural_name="Lines")
    for slug in ("container", "qty", "price"):
        SchemaRegistryService.add_field(workspace_id=other, entity_slug="line", slug=slug,
                                        name=slug.title(),
                                        field_type="text" if slug == "container" else "integer",
                                        is_promoted=True)
    m = [{"name": "n", "query": _q("A"), "aggregate": "count"}]
    assert AggregationService.compute(workspace_id=ws, measures=m, emit=False).values["n"] == 1
    assert AggregationService.compute(workspace_id=other, measures=m, emit=False).values["n"] == 0


@pytest.mark.django_db
def test_emits_audit_event(ws):
    _line(ws, "A", 1, 1)
    AggregationService.compute(workspace_id=ws, source="test",
                               measures=[{"name": "n", "query": _q("A"), "aggregate": "count"}])
    assert DomainEvent.objects.filter(workspace_id=ws, aggregate_type="aggregation").exists()


@pytest.mark.django_db
def test_metrics(ws):
    _line(ws, "A", 1, 1)
    r = AggregationService.compute(
        workspace_id=ws,
        measures=[{"name": "n", "query": _q("A"), "aggregate": "count"}],
        computes=[{"name": "d", "expression": "n * 2"}], emit=False)
    assert r.metrics["measures"] == 1 and r.metrics["computes"] == 1
    assert r.metrics["queries_executed"] == 1 and r.metrics["duration_ms"] >= 0


@pytest.mark.django_db
def test_no_measures_is_empty(ws):
    r = AggregationService.compute(workspace_id=ws, measures=[], emit=False)
    assert r.outputs == {} and not r.errors
