"""
Guard Framework (Platform Gap A) — a reusable, domain-agnostic Core capability for **declarative
cross-record validation**.

The gap it fills (COLLEGE_ARCHITECTURE_ANALYSIS.md §10): Rules/workflow-``condition``/computed
formulas evaluate a **single record** with a **fixed threshold**; rollups aren't recomputed on
child writes; there is no correlated NQL and no generic record locking. So a constraint that
depends on **other records** ("seats used < capacity", "prerequisite completed", "no active hold",
"credit sum ≤ limit", "status in [...]") cannot be expressed.

This framework fills EXACTLY that gap and NOTHING else. It understands only generic concepts —
**query → aggregate → compare → threshold → pass/fail** — and knows nothing about any industry
(School, College, Hospital, Hotel, Inventory, …). It REUSES the single Core query engine
(``execute_nql``) and the event store. Template resolution (``{{record.*}}``) stays with the
CONSUMER (e.g. the workflow executor resolves via the existing ``resolve_value`` before calling in),
so this module depends on no consumer. ``GuardService.evaluate`` is pure + side-effect free (bar an
optional audit event), so ANY consumer — Workflow (first), REST, RecordService, Studio, imports,
bulk actions, approvals — can call it without redesign.

Production-grade: per-evaluation query cache, pluggable operator/aggregate registries (extend
without editing this class), structured errors (no stack traces), optional fail-fast, an optional
transaction/lock hook, and performance metrics — all generic.

A guard rule (dict; values already concrete — the consumer resolved templates):
    {"name": "capacity", "query": <NQL source>, "aggregate": "count", "field": "...",
     "operator": "lt", "threshold": {"query": <NQL>, "aggregate": "value", "field": "capacity"},
     "severity": "block"|"warn", "message": "..."}
aggregate: count | exists | value | sum | avg | min | max | count_distinct | distinct
operator:  exists | not_exists | lt | lte | gt | gte | eq | ne | between | in | not_in |
           contains | starts_with | ends_with
threshold: a literal, a list (between/in), or a nested {query, aggregate, field} measure (dynamic).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass

from apps.nql.services import execute_nql


# ── structured errors (never leak stack traces) ──────────────────────────────
class GuardError(Exception):  # noqa: N818 — domain error
    """Raised only for a programming misuse of the API; per-guard problems are returned as
    structured error entries, never raised."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


# ── typed models ──────────────────────────────────────────────────────────────
@dataclass
class GuardCheck:
    name: str
    aggregate: str
    operator: str
    measured: object
    threshold: object
    ok: bool
    severity: str
    message: str = ""
    error: dict | None = None      # {"code", "message"} when the guard could not be evaluated


@dataclass
class GuardMetrics:
    guards: int = 0
    queries_executed: int = 0
    cache_hits: int = 0
    duration_ms: float = 0.0


@dataclass
class GuardResult:
    passed: bool
    blocked: bool
    failures: list          # block-severity failures (unmet constraints)
    warnings: list          # warn-severity failures
    errors: list            # guards that could not be evaluated (invalid def / nql / threshold)
    checks: list            # every GuardCheck (as dicts)
    metrics: GuardMetrics


# ── aggregate registry (extend without editing GuardService) ─────────────────
def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _field_values(rows, agg_field):
    return [r.get(agg_field) for r in rows] if agg_field else []


AGGREGATES = {
    "count": lambda rows, f: float(len(rows)),
    "exists": lambda rows, f: float(len(rows)),
    "value": lambda rows, f: (rows[0].get(f) if (rows and f) else None),
    "sum": lambda rows, f: float(sum(_to_float(v) for v in _field_values(rows, f))),
    "avg": lambda rows, f: (float(sum(_to_float(v) for v in _field_values(rows, f)) / len(rows))
                            if rows else 0.0),
    "min": lambda rows, f: (min(_to_float(v) for v in _field_values(rows, f)) if rows else 0.0),
    "max": lambda rows, f: (max(_to_float(v) for v in _field_values(rows, f)) if rows else 0.0),
    "count_distinct": lambda rows, f: float(len({str(v) for v in _field_values(rows, f)})),
    "distinct": lambda rows, f: sorted({str(v) for v in _field_values(rows, f)}),
}


def register_aggregate(name: str, fn) -> None:
    """Register a custom aggregate ``fn(rows, field) -> value`` (generic; no domain logic)."""
    AGGREGATES[name.lower()] = fn


# ── operator registry (strategy pattern; extend without editing GuardService) ─
def _eq(m, t):
    try:
        return _to_float(m) == _to_float(t) if _numeric(m) and _numeric(t) else str(m) == str(t)
    except (TypeError, ValueError):
        return str(m) == str(t)


def _numeric(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _between(m, t):
    lo, hi = (list(t or [0, 0]) + [0, 0])[:2]
    return _to_float(lo) <= _to_float(m) <= _to_float(hi)


OPERATORS = {
    "exists": lambda m, t: _to_float(m) > 0,
    "not_exists": lambda m, t: _to_float(m) == 0,
    "lt": lambda m, t: _to_float(m) < _to_float(t),
    "lte": lambda m, t: _to_float(m) <= _to_float(t),
    "gt": lambda m, t: _to_float(m) > _to_float(t),
    "gte": lambda m, t: _to_float(m) >= _to_float(t),
    "eq": _eq,
    "ne": lambda m, t: not _eq(m, t),
    "between": _between,
    "in": lambda m, t: str(m) in [str(x) for x in (t or [])],
    "not_in": lambda m, t: str(m) not in [str(x) for x in (t or [])],
    "contains": lambda m, t: (str(t) in m) if isinstance(m, (list | tuple))
    else (str(t) in str(m)),
    "starts_with": lambda m, t: str(m).startswith(str(t)),
    "ends_with": lambda m, t: str(m).endswith(str(t)),
}
_LIST_THRESHOLD_OPS = {"between", "in", "not_in"}
_NO_THRESHOLD_OPS = {"exists", "not_exists"}


def register_operator(name: str, fn) -> None:
    """Register a custom operator ``fn(measured, threshold) -> bool`` (generic; no domain logic)."""
    OPERATORS[name.lower()] = fn


# ── evaluation ────────────────────────────────────────────────────────────────
class _Cache:
    """Query cache for the lifetime of a single evaluate() — never spans requests."""

    def __init__(self):
        self._rows: dict[str, list] = {}
        self.executed = 0
        self.hits = 0

    def rows(self, workspace_id, query, user_id) -> list:
        key = json.dumps(query, sort_keys=True, default=str)
        if key in self._rows:
            self.hits += 1
            return self._rows[key]
        rows = execute_nql(workspace_id=workspace_id, source=query, user_id=user_id)
        self._rows[key] = rows
        self.executed += 1
        return rows


def _measure(workspace_id, spec: dict, user_id, cache: _Cache):
    query = spec.get("query")
    if query is None:
        raise GuardError("invalid_guard", "a guard/threshold measure requires a 'query'")
    aggregate = (spec.get("aggregate") or "count").lower()
    if aggregate not in AGGREGATES:
        raise GuardError("invalid_aggregate", f"unknown aggregate {aggregate!r}")
    try:
        rows = cache.rows(workspace_id, query, user_id)
    except Exception as exc:  # noqa: BLE001 — any NQL/DB problem → structured error
        raise GuardError("nql_error", f"query failed: {type(exc).__name__}") from exc
    return AGGREGATES[aggregate](rows, spec.get("field"))


def _resolve_threshold(workspace_id, raw, operator, user_id, cache: _Cache):
    if operator in _NO_THRESHOLD_OPS:
        return None
    if operator in _LIST_THRESHOLD_OPS and isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and raw.get("query") is not None:
        try:
            return _measure(workspace_id, raw, user_id, cache)
        except GuardError as exc:
            raise GuardError("threshold_error", exc.args[0]) from exc
    return raw


class GuardService:
    """The single reusable entry point. ``guards`` values are already concrete (the consumer
    resolved any templates). Workspace-scoped (every query runs through ``execute_nql``)."""

    @staticmethod
    def evaluate(*, workspace_id, guards, user_id=None, source="", emit=True,
                 fail_fast=False, lock=False) -> GuardResult:
        """Evaluate guard rules. ``fail_fast`` stops after the first BLOCK failure (default off,
        preserving full evaluation). ``lock=True`` runs inside a DB transaction — the generic
        extension point for future atomic enforcement (Gap B); it adds no hardcoded SQL and reuses
        Django's transaction infrastructure."""
        if lock:
            from django.db import transaction
            with transaction.atomic():
                return GuardService._run(workspace_id, guards, user_id, source, emit, fail_fast)
        return GuardService._run(workspace_id, guards, user_id, source, emit, fail_fast)

    @staticmethod
    def _run(workspace_id, guards, user_id, source, emit, fail_fast) -> GuardResult:
        started = time.perf_counter()
        cache = _Cache()
        failures, warnings, errors, checks = [], [], [], []
        for raw in guards or []:
            severity = (raw.get("severity") or "block") if isinstance(raw, dict) else "block"
            name = raw.get("name", "") if isinstance(raw, dict) else ""
            operator = (raw.get("operator") or "exists").lower() if isinstance(raw, dict) else ""
            aggregate = (raw.get("aggregate") or "count").lower() if isinstance(raw, dict) else ""
            try:
                if not isinstance(raw, dict):
                    raise GuardError("invalid_guard", "guard must be an object")
                if operator not in OPERATORS:
                    raise GuardError("invalid_operator", f"unknown operator {operator!r}")
                measured = _measure(workspace_id, raw, user_id, cache)
                threshold = _resolve_threshold(workspace_id, raw.get("threshold"), operator,
                                               user_id, cache)
                ok = bool(OPERATORS[operator](measured, threshold))
                check = GuardCheck(name=name, aggregate=aggregate, operator=operator,
                                   measured=measured, threshold=threshold, ok=ok, severity=severity,
                                   message=raw.get("message", ""))
            except GuardError as exc:
                # A guard that cannot be evaluated is fail-closed: reported as an error and, for a
                # block-severity guard, counts as blocking (never silently passes).
                check = GuardCheck(name=name, aggregate=aggregate, operator=operator, measured=None,
                                   threshold=None, ok=False, severity=severity,
                                   message=raw.get("message", "") if isinstance(raw, dict) else "",
                                   error={"code": exc.code, "message": exc.args[0]})
                errors.append({"name": name, "code": exc.code, "message": exc.args[0],
                               "severity": severity})
            checks.append(asdict(check))
            if not check.ok:
                entry = {"name": name, "severity": severity, "message": check.message,
                         "measured": check.measured, "threshold": check.threshold,
                         "operator": operator, "aggregate": aggregate}
                if check.error:
                    entry["error"] = check.error
                if severity == "warn":
                    warnings.append(entry)
                else:
                    failures.append(entry)
                    if fail_fast:
                        break

        metrics = GuardMetrics(
            guards=len(checks), queries_executed=cache.executed, cache_hits=cache.hits,
            duration_ms=round((time.perf_counter() - started) * 1000, 3))
        blocked = bool(failures)
        result = GuardResult(passed=not blocked, blocked=blocked, failures=failures,
                             warnings=warnings, errors=errors, checks=checks, metrics=metrics)
        if emit:
            _emit(workspace_id, source, result, user_id)
        return result


def _emit(workspace_id, source, result: GuardResult, user_id):
    """Best-effort audit domain event — never breaks evaluation, never leaks internals."""
    try:
        from apps.eventstore.events import DomainEventData, DomainEventFactory
        summary = [{"name": c["name"], "aggregate": c["aggregate"], "operator": c["operator"],
                    "measured": c["measured"], "threshold": c["threshold"], "ok": c["ok"]}
                   for c in result.checks]
        DomainEventFactory.persist_one(DomainEventData(
            event_type="guard.failed" if result.blocked else "guard.evaluated",
            workspace_id=uuid.UUID(str(workspace_id)), aggregate_type="guard",
            aggregate_id=uuid.uuid4(), version=1,
            payload={"source": source, "passed": result.passed, "blocked": result.blocked,
                     "failures": result.failures, "warnings": result.warnings,
                     "errors": result.errors, "checks": summary,
                     "metrics": asdict(result.metrics)},
            actor_id=uuid.UUID(str(user_id)) if user_id else uuid.UUID(int=0)))
    except Exception:  # noqa: BLE001 — audit is best-effort
        pass
