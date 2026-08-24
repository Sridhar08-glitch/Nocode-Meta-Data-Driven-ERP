"""
NQL Abstract Syntax Tree.

The wire form clients send is the JSON serialization of ``NQLQuery`` (master spec
§12). The lark text parser and the JSON loader both produce these same objects,
which the compiler turns into parameterized SQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .exceptions import NQLSyntaxError, UnknownOperatorError

# Operators supported by NQL v1 (PROJECT_HANDBOOK.md §14 + master spec §12).
COMPARISON_OPS = {
    "=", "!=", ">", ">=", "<", "<=",
    "in", "not in", "contains", "is null", "is not null",
}
NULLARY_OPS = {"is null", "is not null"}      # take no value
LIST_OPS = {"in", "not in"}                   # take a list value
AGG_FUNCS = {"count", "sum", "avg", "min", "max"}
GROUP_OPS = {"and", "or"}


@dataclass
class Condition:
    field: str
    op: str
    value: Any = None

    def __post_init__(self):
        self.op = self.op.lower().strip()
        if self.op not in COMPARISON_OPS:
            raise UnknownOperatorError(f"Unsupported operator: {self.op!r}")


@dataclass
class FilterGroup:
    op: str                       # "and" | "or"
    conditions: list[Any] = field(default_factory=list)   # Condition | FilterGroup

    def __post_init__(self):
        self.op = self.op.lower().strip()
        if self.op not in GROUP_OPS:
            raise NQLSyntaxError(f"Filter group op must be 'and'/'or', got {self.op!r}")


@dataclass
class SortClause:
    field: str
    direction: str = "asc"

    def __post_init__(self):
        self.direction = self.direction.lower().strip()
        if self.direction not in ("asc", "desc"):
            raise NQLSyntaxError(f"Sort direction must be asc/desc, got {self.direction!r}")


@dataclass
class Aggregation:
    func: str
    field: str | None = None      # None ⇒ count(*)
    alias: str | None = None

    def __post_init__(self):
        self.func = self.func.lower().strip()
        if self.func not in AGG_FUNCS:
            raise NQLSyntaxError(f"Unsupported aggregation: {self.func!r}")
        if self.alias is None:
            self.alias = f"{self.func}_{self.field}" if self.field else f"{self.func}_all"


@dataclass
class NQLQuery:
    entity: str
    select: list[str] = field(default_factory=list)
    filter: FilterGroup | None = None
    sort: list[SortClause] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    aggregations: list[Aggregation] = field(default_factory=list)
    limit: int | None = None
    offset: int = 0
    page: int | None = None
    as_of: str | None = None      # time-travel read — accepted, not executed in v1


# ── JSON wire form → AST ─────────────────────────────────────────────────────

def _parse_filter(node: Any) -> Any:
    """Recursively parse a filter node into FilterGroup/Condition."""
    if node is None:
        return None
    if not isinstance(node, dict):
        raise NQLSyntaxError("filter must be an object")
    if "op" in node and "conditions" in node:
        return FilterGroup(
            op=node["op"],
            conditions=[_parse_filter(c) for c in node["conditions"]],
        )
    if "field" in node and "op" in node:
        return Condition(field=node["field"], op=node["op"], value=node.get("value"))
    raise NQLSyntaxError(f"Unrecognised filter node: {node!r}")


def query_from_json(data: dict) -> NQLQuery:
    """Build an NQLQuery from the JSON wire form. Raises NQLSyntaxError on bad shape."""
    if not isinstance(data, dict):
        raise NQLSyntaxError("NQL query must be a JSON object")
    if not data.get("entity"):
        raise NQLSyntaxError("NQL query requires an 'entity'")

    sort = [
        SortClause(field=s["field"], direction=s.get("direction", s.get("dir", "asc")))
        for s in data.get("sort", [])
    ]
    aggregations = [
        Aggregation(func=a["func"], field=a.get("field"), alias=a.get("alias"))
        for a in data.get("aggregations", [])
    ]
    pagination = data.get("pagination") or {}
    return NQLQuery(
        entity=data["entity"],
        select=list(data.get("select", [])),
        filter=_parse_filter(data.get("filter")),
        sort=sort,
        group_by=list(data.get("groupBy", data.get("group_by", []))),
        aggregations=aggregations,
        limit=pagination.get("limit", data.get("limit")),
        offset=pagination.get("offset", data.get("offset", 0)),
        page=pagination.get("page", data.get("page")),
        as_of=data.get("asOf", data.get("as_of")),
    )
