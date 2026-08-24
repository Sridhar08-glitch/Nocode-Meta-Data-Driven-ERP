"""
Aggregation Framework (Platform Gap CG-2) — a reusable, domain-agnostic Core capability for
**declarative cross-record aggregation + calculation + persistence**.

The gap it fills (Platform Gap CG-2): formula fields are single-record; rollup
fields are single-filter, single-field, and never invoked in production; the workflow ``nql_query``
step runs a *static* source; the Guard Framework *validates* (pass/fail) but does not persist a
measured value; Analytics/Reporting *display* aggregates but never write them to a record. So a
**derived value that depends on other records** — a weighted average, a running sum, a ratio,
a min/max over related rows — cannot be computed and stored declaratively.

This framework fills EXACTLY that gap and NOTHING else. It is the **compute-and-persist sibling of
the Guard Framework**: where Guards do *query → aggregate → compare → pass/fail*, Aggregation does
*query → aggregate → calculate → value(s)*. It understands only generic concepts and knows nothing
about any industry (finance, operations, inventory, HR, manufacturing, …). It REUSES the single Core query
engine (``execute_nql`` — SQL-side aggregation, no row materialisation), the safe formula evaluator
(``apps.computed.safe_eval`` — no new expression language), and the event store.

``AggregationService.compute`` is PURE + side-effect-free (bar an optional audit event) — it returns
the computed values and never writes. **Persistence is the consumer's concern** (the workflow
``action_aggregate`` step writes the outputs to a target record via ``RecordService``), so this
module depends on no consumer and ANY consumer — Workflow (first), REST, imports, bulk actions — can
call it without redesign. Template resolution (``{{record.*}}``) also stays with the consumer.

A measure (dict; values already concrete — the consumer resolved templates):
    {"name": "total_qp", "query": <NQL AST {entity, filter}>, "aggregate": "sum", "field": "qp"}
aggregate: count | sum | avg | min | max   (SQL-side, via the NQL compiler)
A compute (dict): {"name": "ratio", "expression": "total_a / total_b if total_b > 0 else 0"}
    — evaluated by ``safe_eval`` over the measure values + earlier computes (sequential).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from apps.computed.services import ComputedError, safe_eval
from apps.nql.services import execute_nql

# SQL-side aggregates the NQL compiler emits as ``func(expr)`` — whitelisted so an aggregate name
# can never reach the SQL string unchecked.
_AGGREGATES = {"count", "sum", "avg", "min", "max"}


class AggregationError(Exception):  # noqa: N818 — domain error
    """Raised only for a programming misuse; per-measure/compute problems are returned as structured
    error entries (fail-closed to ``None``), never raised."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass
class AggregationResult:
    values: dict     # measure name -> aggregated scalar
    computed: dict   # compute name -> derived value (None when it could not be evaluated)
    outputs: dict    # {**values, **computed} — the flat map a consumer persists / injects
    errors: list     # measures/computes that could not be evaluated ({name, code, message})
    metrics: dict


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _measure(workspace_id, spec: dict, user_id) -> object:
    """Run ONE record-parameterised aggregation via NQL and return the scalar (0 when empty)."""
    if not isinstance(spec, dict) or not spec.get("name"):
        raise AggregationError("invalid_measure", "a measure requires a 'name'")
    name = spec["name"]
    query = spec.get("query")
    if not isinstance(query, dict) or not query.get("entity"):
        raise AggregationError("invalid_measure", f"measure {name!r} needs a 'query' with an entity")
    aggregate = (spec.get("aggregate") or "count").lower()
    if aggregate not in _AGGREGATES:
        raise AggregationError("invalid_aggregate", f"unknown aggregate {aggregate!r}")
    field = spec.get("field")
    if aggregate != "count" and not field:
        raise AggregationError("invalid_measure", f"aggregate {aggregate!r} on {name!r} needs a field")
    # Push the aggregation into the query so it runs SQL-side (no row materialisation / LIMIT cap).
    q = {k: v for k, v in query.items() if k != "select"}
    q["aggregations"] = [{"func": aggregate, "field": field, "alias": "v"}]
    try:
        rows = execute_nql(workspace_id=workspace_id, source=q, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — any NQL/DB problem → structured error
        raise AggregationError("nql_error", f"query for {name!r} failed: {type(exc).__name__}") from exc
    value = rows[0].get("v") if rows else None
    return value if value is not None else 0


class AggregationService:
    """The single reusable entry point. ``measures``/``computes`` values are already concrete (the
    consumer resolved any templates). Workspace-scoped (every query runs through ``execute_nql``).
    PURE — never persists; the consumer writes the returned ``outputs``."""

    @staticmethod
    def compute(*, workspace_id, measures, computes=None, user_id=None, source="",
                emit=True) -> AggregationResult:
        started = time.perf_counter()
        values, errors, queries = {}, [], 0
        for spec in measures or []:
            name = spec.get("name") if isinstance(spec, dict) else None
            try:
                values[name] = _measure(workspace_id, spec, user_id)
                queries += 1
            except AggregationError as exc:
                # Fail-closed: a measure that cannot be evaluated is None + a structured error.
                if name:
                    values[name] = None
                errors.append({"name": name, "code": exc.code, "message": exc.args[0]})

        computed: dict = {}
        env = {k: _num(v) for k, v in values.items()}   # numeric env for safe_eval
        for spec in computes or []:
            cname = spec.get("name") if isinstance(spec, dict) else None
            expr = spec.get("expression") if isinstance(spec, dict) else None
            if not cname or not expr:
                errors.append({"name": cname, "code": "invalid_compute",
                               "message": "a compute requires a 'name' and 'expression'"})
                continue
            try:
                result = safe_eval(expr, env)
            except (ComputedError, ZeroDivisionError, TypeError, ValueError) as exc:
                computed[cname] = None
                errors.append({"name": cname, "code": "compute_error",
                               "message": type(exc).__name__})
                continue
            computed[cname] = result
            env[cname] = _num(result)

        outputs = {**values, **computed}
        metrics = {"measures": len(measures or []), "computes": len(computes or []),
                   "queries_executed": queries,
                   "duration_ms": round((time.perf_counter() - started) * 1000, 3)}
        result = AggregationResult(values=values, computed=computed, outputs=outputs,
                                   errors=errors, metrics=metrics)
        if emit:
            _emit(workspace_id, source, result, user_id)
        return result


def _emit(workspace_id, source, result: AggregationResult, user_id):
    """Best-effort audit domain event — never breaks the computation, never leaks internals."""
    try:
        from apps.eventstore.events import DomainEventData, DomainEventFactory
        DomainEventFactory.persist_one(DomainEventData(
            event_type="aggregation.failed" if result.errors else "aggregation.computed",
            workspace_id=uuid.UUID(str(workspace_id)), aggregate_type="aggregation",
            aggregate_id=uuid.uuid4(), version=1,
            payload={"source": source, "outputs": result.outputs, "errors": result.errors,
                     "metrics": result.metrics},
            actor_id=uuid.UUID(str(user_id)) if user_id else uuid.UUID(int=0)))
    except Exception:  # noqa: BLE001 — audit is best-effort
        pass
