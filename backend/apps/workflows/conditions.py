"""
In-memory NQL condition evaluation + value resolution for the workflow engine.

Workflow triggers, ``condition`` steps and edge guards all reuse the NQL filter
grammar but are evaluated **in-memory** against the run context / trigger record
(never compiled to SQL — there is no table to query at decision time). This is the
same approach the Business Rules engine takes (``apps/rules/services.py``); the
logic is duplicated here deliberately so the workflow engine carries no import
dependency on the rules app.

``resolve_value`` lets step configs reference run-context data and server-side
magic values safely:

    "@me", "@today", ...     → resolved via :class:`NQLContext`
    "{{record.status}}"      → dotted lookup into the run context
    anything else            → returned verbatim
"""
from __future__ import annotations

import re

from apps.nql.ast import Condition, FilterGroup
from apps.nql.context import NQLContext
from apps.nql.exceptions import NQLError
from apps.nql.parser import parse_nql_text

_TEMPLATE_RE = re.compile(r"^\{\{\s*([\w.]+)\s*\}\}$")


def parse_condition(entity_slug: str, condition_nql: str):
    """Parse an NQL ``WHERE`` fragment into a filter node (or ``None`` = always true)."""
    if not condition_nql or not condition_nql.strip():
        return None
    query = parse_nql_text(f"FROM {entity_slug or '_'} WHERE {condition_nql}")
    return query.filter


def _eval_cond(cond: Condition, record: dict, ctx: NQLContext) -> bool:
    lhs = record.get(cond.field)
    op = cond.op
    rhs = ctx.resolve_magic(cond.value) if isinstance(cond.value, str) else cond.value
    if op == "is null":
        return lhs is None
    if op == "is not null":
        return lhs is not None
    if op == "in":
        return str(lhs) in [str(v) for v in (rhs or [])]
    if op == "not in":
        return str(lhs) not in [str(v) for v in (rhs or [])]
    if op == "contains":
        return rhs is not None and str(rhs) in str(lhs or "")
    if lhs is None:
        return False
    if op == "=":
        return str(lhs) == str(rhs)
    if op == "!=":
        return str(lhs) != str(rhs)
    try:
        lf, rf = float(lhs), float(rhs)
    except (TypeError, ValueError):
        return False
    return {">": lf > rf, ">=": lf >= rf, "<": lf < rf, "<=": lf <= rf}.get(op, False)


def eval_node(node, record: dict, ctx: NQLContext) -> bool:
    """Evaluate a parsed NQL filter node against ``record`` in memory."""
    if node is None:
        return True
    if isinstance(node, Condition):
        return _eval_cond(node, record, ctx)
    if isinstance(node, FilterGroup):
        results = [eval_node(c, record, ctx) for c in node.conditions]
        return all(results) if node.op == "and" else any(results)
    return True


def evaluate(condition_nql: str, record: dict, *, workspace_id, user_id=None,
             entity_slug: str = "") -> bool:
    """Parse + evaluate an NQL condition string against ``record``.

    An empty/blank condition is always true. A condition that fails to parse is
    treated as *not matched* (fail-closed) so a malformed guard never fires a
    branch or trigger by accident.
    """
    ctx = NQLContext(workspace_id=workspace_id, user_id=user_id)
    try:
        node = parse_condition(entity_slug, condition_nql)
    except NQLError:
        return False
    return eval_node(node, record, ctx)


def resolve_value(value, context: dict, *, workspace_id, user_id=None):
    """Resolve a single step-config value against the run context.

    - ``"@me"`` / ``"@today"`` / … → server-side magic value
    - ``"{{a.b.c}}"``             → dotted lookup into ``context``
    - lists / dicts              → resolved recursively
    - everything else            → returned unchanged
    """
    if isinstance(value, list):
        return [resolve_value(v, context, workspace_id=workspace_id, user_id=user_id)
                for v in value]
    if isinstance(value, dict):
        return {k: resolve_value(v, context, workspace_id=workspace_id, user_id=user_id)
                for k, v in value.items()}
    if not isinstance(value, str):
        return value
    if value.startswith("@"):
        ctx = NQLContext(workspace_id=workspace_id, user_id=user_id)
        try:
            return ctx.resolve_magic(value)
        except ValueError:
            return value
    m = _TEMPLATE_RE.match(value)
    if m:
        cur = context
        for part in m.group(1).split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
    return value


def resolve_mapping(mapping: dict, context: dict, *, workspace_id, user_id=None) -> dict:
    """Resolve every value in a ``{field: value}`` config mapping."""
    return {k: resolve_value(v, context, workspace_id=workspace_id, user_id=user_id)
            for k, v in (mapping or {}).items()}
