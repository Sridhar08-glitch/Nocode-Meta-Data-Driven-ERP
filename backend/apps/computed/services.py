"""
Computed Fields Engine (master spec §39).

- ``formula`` fields: single-record expressions (``price * quantity * (1 - discount)``)
  evaluated by a **safe AST evaluator — never eval()** (§9.2). A dependency DAG over
  formula fields is cycle-checked; formulas compute in topological order so one
  formula may reference another.
- ``rollup`` fields: cross-entity aggregations (``SUM(children.amount)``) computed
  via NQL.
"""
from __future__ import annotations

import ast
import operator

from apps.nql.services import execute_nql

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}
_CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}


class ComputedError(Exception):
    pass


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _eval(node, names):
    if isinstance(node, ast.Expression):
        return _eval(node.body, names)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names.get(node.id, 0)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, names), _eval(node.right, names))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, names)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return +_eval(node.operand, names)
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, names) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
        return _CMP[type(node.ops[0])](_eval(node.left, names), _eval(node.comparators[0], names))
    if isinstance(node, ast.IfExp):
        return _eval(node.body, names) if _eval(node.test, names) else _eval(node.orelse, names)
    raise ComputedError(f"Unsupported expression element: {type(node).__name__}")


def safe_eval(expression: str, names: dict):
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ComputedError(f"Invalid formula: {expression!r}") from exc
    return _eval(tree, names)


def _referenced_names(expression: str) -> set:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _topo_order(formula_fields):
    """Return formula fields in dependency order; raise ComputedError on a cycle."""
    by_slug = {f.slug: f for f in formula_fields}
    deps = {f.slug: (_referenced_names((f.config or {}).get("expression", "")) & set(by_slug))
            for f in formula_fields}
    order, visited, stack = [], set(), set()

    def visit(slug):
        if slug in visited:
            return
        if slug in stack:
            raise ComputedError(f"Circular formula dependency at {slug!r}")
        stack.add(slug)
        for d in deps[slug]:
            visit(d)
        stack.discard(slug)
        visited.add(slug)
        order.append(by_slug[slug])

    for slug in by_slug:
        visit(slug)
    return order


def compute_fields(entity, values: dict) -> dict:
    """Return ``{formula_slug: value}`` computed from *values* (the full record)."""
    fields = list(entity.fields.filter(is_deleted=False))
    formula_fields = [f for f in fields if f.field_type == "formula"]
    if not formula_fields:
        return {}
    names = {f.slug: _num(values.get(f.slug)) for f in fields}
    out = {}
    for f in _topo_order(formula_fields):            # raises on cycle
        expr = (f.config or {}).get("expression", "")
        if not expr:
            continue
        result = safe_eval(expr, names)
        out[f.slug] = result
        names[f.slug] = _num(result)
    return out


def compute_rollup(entity, parent_record_id, rollup_field) -> object:
    """Aggregate child records for a ``rollup`` field via NQL.

    config = {source_entity_slug, match_field, agg(sum|avg|count|min|max), field?}.
    """
    cfg = rollup_field.config or {}
    source = cfg.get("source_entity_slug")
    match_field = cfg.get("match_field")
    agg = (cfg.get("agg") or "count").lower()
    field = cfg.get("field")
    if not source or not match_field:
        raise ComputedError("rollup requires source_entity_slug + match_field")
    query = {
        "entity": source,
        "filter": {"op": "and", "conditions": [
            {"field": match_field, "op": "=", "value": str(parent_record_id)}]},
        "aggregations": [{"func": agg, "field": field, "alias": "v"}],
    }
    rows = execute_nql(workspace_id=entity.workspace_id, source=query)
    return rows[0]["v"] if rows else 0
