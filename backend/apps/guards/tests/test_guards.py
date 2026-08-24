"""
Guard Framework (Platform Gap A) certification — the reusable, domain-agnostic cross-record
validation capability. Proves every aggregate + operator + dynamic thresholds + severity + multi-
guard + workspace isolation + audit events, over generic metadata entities (nothing education- or
package-specific). SQLite + PostgreSQL.
"""
import uuid

import pytest

from apps.eventstore.models import DomainEvent
from apps.guards.services import GuardService
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member


@pytest.fixture
def ws(db):
    """A workspace with two generic entities: `cap_item` (capacity) + `booking` (item/status/credits)."""
    w = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=w, slug="cap_item", name="Cap Item",
                                        plural_name="Cap Items")
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="cap_item", slug="name",
                                    name="Name", field_type="text", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=w, entity_slug="cap_item", slug="capacity",
                                    name="Capacity", field_type="integer", is_promoted=True)
    SchemaRegistryService.create_entity(workspace_id=w, slug="booking", name="Booking",
                                        plural_name="Bookings")
    for slug, ft in [("item", "text"), ("status", "text"), ("credits", "integer")]:
        SchemaRegistryService.add_field(workspace_id=w, entity_slug="booking", slug=slug,
                                        name=slug.title(), field_type=ft, is_promoted=True)
    return w


def _rec(ws, slug, data):
    from apps.metadata.models import EntityDefinition
    entity = EntityDefinition.objects.get(workspace_id=ws, slug=slug)
    return RecordService.create_record(workspace_id=ws, member=system_member(None), entity=entity,
                                       data=data)


def _q(entity, **eq):
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    return {"entity": entity, "filter": {"op": "and", "conditions": conds}}


def _confirmed(ws, item="A", n=1, credits=3):
    for _ in range(n):
        _rec(ws, "booking", {"item": item, "status": "confirmed", "credits": credits})


# ── operators + aggregates ────────────────────────────────────────────────────
@pytest.mark.django_db
def test_count_lt_static_threshold(ws):
    _confirmed(ws, "A", 1)
    g = {"name": "cap", "query": _q("booking", item="A", status="confirmed"),
         "aggregate": "count", "operator": "lt", "threshold": 2, "message": "full"}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).passed          # 1 < 2
    _confirmed(ws, "A", 1)
    r = GuardService.evaluate(workspace_id=ws, guards=[g])
    assert r.blocked and r.failures[0]["name"] == "cap"                       # 2 not < 2


@pytest.mark.django_db
def test_dynamic_threshold_from_query(ws):
    """Capacity as a DYNAMIC threshold measured from another record (no denormalization)."""
    _rec(ws, "cap_item", {"name": "A", "capacity": 2})
    _confirmed(ws, "A", 2)
    g = {"name": "capacity", "query": _q("booking", item="A", status="confirmed"),
         "aggregate": "count", "operator": "lt",
         "threshold": {"query": _q("cap_item", name="A"), "aggregate": "value", "field": "capacity"}}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).blocked         # 2 not < 2
    _rec(ws, "cap_item", {"name": "B", "capacity": 5})
    g2 = {**g, "query": _q("booking", item="B", status="confirmed"),
          "threshold": {"query": _q("cap_item", name="B"), "aggregate": "value", "field": "capacity"}}
    assert GuardService.evaluate(workspace_id=ws, guards=[g2]).passed         # 0 < 5


@pytest.mark.django_db
def test_exists_and_not_exists(ws):
    _rec(ws, "booking", {"item": "A", "status": "hold"})
    exists = {"name": "prereq", "query": _q("booking", item="A"), "operator": "exists"}
    assert GuardService.evaluate(workspace_id=ws, guards=[exists]).passed
    no_hold = {"name": "no_hold", "query": _q("booking", item="A", status="hold"),
               "operator": "not_exists", "message": "has a hold"}
    assert GuardService.evaluate(workspace_id=ws, guards=[no_hold]).blocked
    ok_hold = {**no_hold, "query": _q("booking", item="Z", status="hold")}
    assert GuardService.evaluate(workspace_id=ws, guards=[ok_hold]).passed


@pytest.mark.django_db
def test_sum_avg_min_max(ws):
    for c in (3, 4, 5):
        _rec(ws, "booking", {"item": "A", "status": "confirmed", "credits": c})
    base = _q("booking", item="A", status="confirmed")
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {"query": base, "aggregate": "sum", "field": "credits", "operator": "lte",
         "threshold": 12}]).passed                                            # 12 <= 12
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {"query": base, "aggregate": "sum", "field": "credits", "operator": "lte",
         "threshold": 11}]).blocked                                           # 12 not <= 11
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {"query": base, "aggregate": "avg", "field": "credits", "operator": "eq",
         "threshold": 4}]).passed                                            # avg=4
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {"query": base, "aggregate": "max", "field": "credits", "operator": "lte",
         "threshold": 5}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {"query": base, "aggregate": "min", "field": "credits", "operator": "gte",
         "threshold": 3}]).passed


@pytest.mark.django_db
def test_between(ws):
    _confirmed(ws, "A", 2)
    g = {"query": _q("booking", item="A"), "aggregate": "count", "operator": "between",
         "threshold": [1, 3]}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).passed          # 1<=2<=3


# ── severity, multi-guard, isolation, audit ──────────────────────────────────
@pytest.mark.django_db
def test_warn_does_not_block(ws):
    _confirmed(ws, "A", 5)
    g = {"name": "soft", "query": _q("booking", item="A"), "aggregate": "count",
         "operator": "lt", "threshold": 2, "severity": "warn", "message": "getting full"}
    r = GuardService.evaluate(workspace_id=ws, guards=[g])
    assert r.passed and not r.blocked and len(r.warnings) == 1 and not r.failures


@pytest.mark.django_db
def test_multiple_guards_any_block_fails(ws):
    _rec(ws, "cap_item", {"name": "A", "capacity": 10})
    _confirmed(ws, "A", 1)
    guards = [
        {"name": "capacity", "query": _q("booking", item="A", status="confirmed"),
         "aggregate": "count", "operator": "lt", "threshold": 10},          # passes
        {"name": "no_hold", "query": _q("booking", item="A", status="hold"),
         "operator": "not_exists"},                                          # passes
        {"name": "must_prereq", "query": _q("booking", item="A", status="prereq"),
         "operator": "exists", "message": "missing prereq"},                # fails (none)
    ]
    r = GuardService.evaluate(workspace_id=ws, guards=guards)
    assert r.blocked and [f["name"] for f in r.failures] == ["must_prereq"]
    assert len(r.checks) == 3


@pytest.mark.django_db
def test_workspace_isolation(ws):
    _confirmed(ws, "A", 3)
    # a different workspace that has the SAME entity but no rows must measure 0 (isolation)
    other = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=other, slug="booking", name="Booking",
                                        plural_name="Bookings")
    for slug in ("item", "status", "credits"):
        SchemaRegistryService.add_field(workspace_id=other, entity_slug="booking", slug=slug,
                                        name=slug.title(),
                                        field_type="integer" if slug == "credits" else "text",
                                        is_promoted=True)
    g = {"query": _q("booking", item="A"), "aggregate": "count", "operator": "gt", "threshold": 0}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).passed          # 3 > 0
    assert GuardService.evaluate(workspace_id=other, guards=[g]).blocked      # 0 not > 0 (isolated)


# ── production-grade: cache, fail-fast, new operators, distinct, errors, metrics ──
@pytest.mark.django_db
def test_query_cache_dedupes_identical_nql(ws):
    _confirmed(ws, "A", 1)
    same = _q("booking", item="A", status="confirmed")
    r = GuardService.evaluate(workspace_id=ws, guards=[
        {"name": "g1", "query": same, "aggregate": "count", "operator": "gte", "threshold": 1},
        {"name": "g2", "query": same, "aggregate": "count", "operator": "lt", "threshold": 5},
    ])
    assert r.metrics.guards == 2
    assert r.metrics.queries_executed == 1 and r.metrics.cache_hits == 1   # ran the NQL once
    assert r.metrics.duration_ms >= 0


@pytest.mark.django_db
def test_fail_fast_stops_after_first_block(ws):
    guards = [
        {"name": "first", "query": _q("booking", item="X"), "operator": "exists",
         "message": "missing"},                                  # fails (0 rows)
        {"name": "second", "query": _q("booking", item="Y"), "operator": "exists"},  # would also fail
    ]
    full = GuardService.evaluate(workspace_id=ws, guards=guards)
    assert len(full.failures) == 2                               # default: evaluate all
    fast = GuardService.evaluate(workspace_id=ws, guards=guards, fail_fast=True)
    assert len(fast.failures) == 1 and fast.failures[0]["name"] == "first"


@pytest.mark.django_db
def test_value_string_operators(ws):
    _rec(ws, "booking", {"item": "A", "status": "open"})
    val = {"query": _q("booking", item="A"), "aggregate": "value", "field": "status"}
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "in", "threshold": ["open", "waitlisting"]}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "not_in", "threshold": ["closed"]}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "starts_with", "threshold": "op"}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "ends_with", "threshold": "en"}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "contains", "threshold": "pe"}]).passed
    assert GuardService.evaluate(workspace_id=ws, guards=[
        {**val, "operator": "in", "threshold": ["closed"]}]).blocked


@pytest.mark.django_db
def test_count_distinct(ws):
    for it in ("A", "A", "B"):
        _rec(ws, "booking", {"item": it, "status": "confirmed"})
    g = {"query": _q("booking", status="confirmed"), "aggregate": "count_distinct",
         "field": "item", "operator": "eq", "threshold": 2}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).passed   # {A,B} → 2


@pytest.mark.django_db
def test_structured_errors_are_fail_closed(ws):
    # unknown aggregate / operator / missing query / bad entity → structured error, blocked
    bad = [
        {"name": "agg", "query": _q("booking"), "aggregate": "median", "operator": "gt",
         "threshold": 1},
        {"name": "op", "query": _q("booking"), "operator": "matches", "threshold": 1},
        {"name": "noq", "operator": "exists"},
        {"name": "ent", "query": _q("does_not_exist"), "operator": "exists"},
    ]
    r = GuardService.evaluate(workspace_id=ws, guards=bad)
    codes = {e["code"] for e in r.errors}
    assert codes == {"invalid_aggregate", "invalid_operator", "invalid_guard", "nql_error"}
    assert r.blocked and len(r.failures) == 4          # all fail-closed
    # no stack traces leaked — only code + message
    assert all(set(e) == {"name", "code", "message", "severity"} for e in r.errors)


@pytest.mark.django_db
def test_register_custom_operator(ws):
    from apps.guards.services import register_operator
    register_operator("is_zero", lambda m, t: float(m) == 0)
    g = {"query": _q("booking", item="none"), "aggregate": "count", "operator": "is_zero"}
    assert GuardService.evaluate(workspace_id=ws, guards=[g]).passed   # 0 rows → is_zero


@pytest.mark.django_db
def test_emits_audit_event(ws):
    _confirmed(ws, "A", 1)
    GuardService.evaluate(workspace_id=ws, guards=[
        {"query": _q("booking", item="A"), "operator": "exists"}], source="test")
    assert DomainEvent.objects.filter(workspace_id=ws, aggregate_type="guard").exists()


@pytest.mark.django_db
def test_no_guards_passes(ws):
    r = GuardService.evaluate(workspace_id=ws, guards=[])
    assert r.passed and not r.blocked and r.checks == []
