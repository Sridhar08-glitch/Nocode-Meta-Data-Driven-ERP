"""
NQL compiler / planner.

Turns an :class:`NQLQuery` into a single parameterized SQL SELECT against an
entity's physical table. Guarantees (master spec §12 / PROJECT_HANDBOOK.md §14):

  * Every referenced field is validated against the entity's FieldDefinition
    (or is a known system column) — unknown fields are rejected.
  * Each field resolves to a promoted physical column OR a ``custom_data`` JSONB
    path, vendor-aware (PostgreSQL ``->>`` / SQLite ``json_extract``).
  * Values are ALWAYS bound parameters — user input is never interpolated.
  * Results are scoped to ``workspace_id`` and exclude soft-deleted rows.
  * ``limit`` is capped at ``settings.NEXUS_NQL_MAX_LIMIT``.
"""
from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import connection

from .ast import Aggregation, Condition, FilterGroup, NQLQuery
from .context import NQLContext
from .exceptions import NQLValueError, UnknownFieldError

_SAFE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# field_type → comparison category
_NUMERIC = {"integer", "number", "decimal", "currency", "percentage", "rating",
            "auto_number", "formula", "rollup"}
_UUIDISH = {"lookup", "user", "uuid"}
_DATETIME = {"date", "datetime", "time", "created_at", "updated_at"}

# system columns present on every generated table, with their category
_SYSTEM_COLUMNS = {
    "id": "uuid", "workspace_id": "uuid",
    "created_by": "uuid", "updated_by": "uuid", "deleted_by": "uuid",
    "created_at": "datetime", "updated_at": "datetime", "deleted_at": "datetime",
}


@dataclass
class NQLResult:
    sql: str
    params: list
    where_sql: str
    order_by: str
    limit: int
    offset: int


def _category(field_type: str) -> str:
    if field_type in _NUMERIC:
        return "numeric"
    if field_type in _UUIDISH:
        return "uuid"
    if field_type == "boolean":
        return "boolean"
    if field_type in _DATETIME:
        return "datetime"
    return "text"


def _assert_ident(name: str) -> str:
    if not _SAFE.match(name):
        raise UnknownFieldError(f"Unsafe identifier: {name!r}")
    return name


class NQLCompiler:
    def __init__(self, entity, context: NQLContext, *, vendor: str | None = None):
        self.entity = entity
        self.ctx = context
        self.vendor = vendor or connection.vendor
        # slug -> (is_promoted, column_name, category)
        self._fields: dict[str, tuple[bool, str, str]] = {}
        for fd in entity.fields.filter(is_deleted=False):
            col = fd.column_name or fd.slug
            self._fields[fd.slug] = (fd.is_promoted, col, _category(fd.field_type))

    # ── field resolution ─────────────────────────────────────────────────────
    def _resolve(self, fieldname: str, *, as_text: bool = False) -> tuple[str, str]:
        """Return (sql_expr, category) for a field reference."""
        if fieldname in _SYSTEM_COLUMNS:
            _assert_ident(fieldname)
            return f'"{fieldname}"', _SYSTEM_COLUMNS[fieldname]
        if fieldname not in self._fields:
            raise UnknownFieldError(
                f"Unknown field {fieldname!r} on entity {self.entity.slug!r}")
        is_promoted, col, cat = self._fields[fieldname]
        if is_promoted:
            return f'"{_assert_ident(col)}"', cat
        # JSONB overflow path
        _assert_ident(fieldname)
        if self.vendor == "postgresql":
            base = f"custom_data->>'{fieldname}'"
            if as_text or cat == "text" or cat == "uuid":
                return base, cat
            if cat == "numeric":
                return f"({base})::numeric", cat
            if cat == "boolean":
                return f"({base})::boolean", cat
            if cat == "datetime":
                return f"({base})::timestamptz", cat
            return base, cat
        # SQLite
        return f"json_extract(custom_data, '$.{fieldname}')", cat

    # ── value coercion + placeholders ─────────────────────────────────────────
    def _placeholder(self, category: str, is_jsonb_text_uuid: bool) -> str:
        if self.vendor != "postgresql":
            return "%s"
        if category == "uuid" and not is_jsonb_text_uuid:
            return "%s::uuid"
        if category == "datetime":
            return "%s::timestamptz"
        return "%s"

    def _coerce(self, value, category: str):
        value = self.ctx.resolve_magic(value)
        try:
            if category == "numeric":
                return float(value) if "." in str(value) else int(value)
            if category == "boolean":
                truthy = str(value).lower() in ("true", "1", "yes", "t")
                return truthy if self.vendor == "postgresql" else int(truthy)
            return str(value)
        except (TypeError, ValueError) as exc:
            raise NQLValueError(f"Bad value {value!r} for {category} field") from exc

    # ── conditions ─────────────────────────────────────────────────────────────
    def _compile_condition(self, cond: Condition) -> tuple[str, list]:
        op = cond.op
        if op in ("is null", "is not null"):
            expr, _ = self._resolve(cond.field, as_text=True)
            return f"{expr} {'IS NULL' if op == 'is null' else 'IS NOT NULL'}", []

        if op == "contains":
            expr, _ = self._resolve(cond.field, as_text=True)
            like = "ILIKE" if self.vendor == "postgresql" else "LIKE"
            val = self.ctx.resolve_magic(cond.value)
            return f"{expr} {like} %s", [f"%{val}%"]

        if op in ("in", "not in"):
            if not isinstance(cond.value, list | tuple):
                raise NQLValueError(f"{op!r} requires a list value")
            expr, cat = self._resolve(cond.field)
            is_jsonb_uuid = cat == "uuid" and "custom_data" in expr
            ph = self._placeholder(cat, is_jsonb_uuid)
            placeholders = ", ".join(ph for _ in cond.value)
            params = [self._coerce(v, cat) for v in cond.value]
            keyword = "IN" if op == "in" else "NOT IN"
            return f"{expr} {keyword} ({placeholders})", params

        # binary comparison
        expr, cat = self._resolve(cond.field)
        is_jsonb_uuid = cat == "uuid" and "custom_data" in expr
        ph = self._placeholder(cat, is_jsonb_uuid)
        return f"{expr} {op} {ph}", [self._coerce(cond.value, cat)]

    def _compile_filter(self, node) -> tuple[str, list]:
        if isinstance(node, Condition):
            return self._compile_condition(node)
        if isinstance(node, FilterGroup):
            parts, params = [], []
            for child in node.conditions:
                sql, p = self._compile_filter(child)
                parts.append(sql)
                params.extend(p)
            if not parts:
                return "", []
            joiner = " AND " if node.op == "and" else " OR "
            return "(" + joiner.join(parts) + ")", params
        raise UnknownFieldError(f"Bad filter node: {node!r}")

    # ── select / aggregations ─────────────────────────────────────────────────
    def _select_clause(self, query: NQLQuery) -> str:
        if query.aggregations:
            cols = []
            for agg in query.aggregations:
                cols.append(self._agg_sql(agg))
            for g in query.group_by:
                expr, _ = self._resolve(g)
                cols.append(f'{expr} AS "{_assert_ident(g)}"')
            return ", ".join(cols)
        if query.select:
            cols = []
            for fname in query.select:
                expr, _ = self._resolve(fname)
                cols.append(f'{expr} AS "{_assert_ident(fname)}"')
            return ", ".join(cols)
        return "*"

    def _agg_sql(self, agg: Aggregation) -> str:
        alias = _assert_ident(agg.alias)
        if agg.func == "count" and not agg.field:
            return f'count(*) AS "{alias}"'
        expr, _ = self._resolve(agg.field)
        return f'{agg.func}({expr}) AS "{alias}"'

    # ── full query ─────────────────────────────────────────────────────────────
    def compile(self, query: NQLQuery) -> NQLResult:
        table = _assert_ident(self.entity.table_name)
        params: list = []

        # Scoping: workspace + soft-delete (the mandatory ORM-layer defense).
        ws_val = (self.ctx.workspace_id if self.vendor == "postgresql"
                  else str(self.ctx.workspace_id))
        ws_ph = "%s::uuid" if self.vendor == "postgresql" else "%s"
        where_parts = [f'"workspace_id" = {ws_ph}', '"deleted_at" IS NULL']
        params.append(ws_val if self.vendor != "postgresql" else _uuid.UUID(str(ws_val)))

        if query.filter is not None:
            sql, p = self._compile_filter(query.filter)
            if sql:
                where_parts.append(sql)
                params.extend(p)
        where_sql = " AND ".join(where_parts)

        group_sql = ""
        if query.group_by:
            group_sql = " GROUP BY " + ", ".join(
                self._resolve(g)[0] for g in query.group_by)

        order_sql = ""
        if query.sort:
            order_terms = []
            for s in query.sort:
                expr, _ = self._resolve(s.field)
                order_terms.append(f"{expr} {'DESC' if s.direction == 'desc' else 'ASC'}")
            order_sql = ", ".join(order_terms)

        # Pagination — cap the limit, honor page if given.
        cap = settings.NEXUS_NQL_MAX_LIMIT
        limit = query.limit if query.limit is not None else cap
        limit = max(0, min(int(limit), cap))
        offset = int(query.offset or 0)
        if query.page and query.page > 0 and query.limit:
            offset = (int(query.page) - 1) * int(query.limit)

        sql = f'SELECT {self._select_clause(query)} FROM "{table}" WHERE {where_sql}'
        if group_sql:
            sql += group_sql
        if order_sql:
            sql += f" ORDER BY {order_sql}"
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return NQLResult(sql=sql, params=params, where_sql=where_sql,
                         order_by=order_sql, limit=limit, offset=offset)
