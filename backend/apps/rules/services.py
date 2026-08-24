"""
Business Rules Engine (master spec §38 / Pillar 9) — DECISIONS, separate from
workflows (processes). A rule is ``IF <condition> THEN <actions>`` evaluated
synchronously when a record is saved.

Conditions reuse the NQL filter grammar (``condition_nql``) but are evaluated
**in-memory** against the record being saved (no SQL). ``before_*`` actions may
mutate or block the write; ``after_*`` actions are side effects.
"""
from __future__ import annotations

import uuid

from apps.nql.ast import Condition, FilterGroup
from apps.nql.context import NQLContext
from apps.nql.exceptions import NQLError
from apps.nql.parser import parse_nql_text

from .models import BusinessRule, RuleExecutionLog


class RuleBlocked(Exception):  # noqa: N818 — control-flow signal, not an error suffix
    """Raised when a before_* rule blocks the save."""


def parse_condition(entity_slug: str, condition_nql: str):
    if not condition_nql or not condition_nql.strip():
        return None  # no condition ⇒ always fires
    query = parse_nql_text(f"FROM {entity_slug} WHERE {condition_nql}")
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


def _eval_node(node, record: dict, ctx: NQLContext) -> bool:
    if node is None:
        return True
    if isinstance(node, Condition):
        return _eval_cond(node, record, ctx)
    if isinstance(node, FilterGroup):
        results = [_eval_node(c, record, ctx) for c in node.conditions]
        return all(results) if node.op == "and" else any(results)
    return True


class RuleEngine:
    @staticmethod
    def apply(entity, record_data: dict, trigger: str, member, *, record_id=None):
        """Run active rules for ``entity`` + ``trigger`` in priority order.

        Returns ``(data, blocked, executed_slugs)``. ``before_*`` triggers may mutate
        ``data`` (set_field) or set ``blocked``; ``after_*`` run for side effects.
        """
        rules = (BusinessRule.objects
                 .filter(workspace_id=entity.workspace_id, entity_id=entity.id,
                         trigger_on=trigger, is_active=True)
                 .order_by("priority"))
        ctx = NQLContext(workspace_id=entity.workspace_id,
                         user_id=member.user_id if member else None)
        data = dict(record_data)
        blocked = False
        executed = []
        for rule in rules:
            try:
                node = parse_condition(entity.slug, rule.condition_nql)
                matched = _eval_node(node, data, ctx)
            except NQLError:
                matched = False
            done = []
            if matched:
                for action in rule.actions:
                    atype = action.get("type")
                    if atype == "set_field":
                        data[action["field"]] = action.get("value")
                        done.append(action)
                    elif atype == "block_save":
                        blocked = True
                        done.append(action)
                executed.append(rule.slug)
            RuleExecutionLog.objects.create(
                rule_id=rule.id, workspace_id=entity.workspace_id,
                record_id=record_id or uuid.UUID(int=0), entity_id=entity.id,
                trigger_on=trigger, condition_matched=matched, actions_executed=done,
                actor_id=member.user_id if member else None)
            if blocked:
                break
            if matched and not rule.run_all:
                break
        return data, blocked, executed
