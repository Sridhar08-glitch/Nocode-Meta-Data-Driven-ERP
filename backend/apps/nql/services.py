"""
NQL orchestration: parse (text or JSON) → resolve entity → compile → execute.

This is the single read path every surface (REST, reports, dashboards, query
builder) goes through (master spec §12). It never executes raw user SQL.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import connection

from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .ast import NQLQuery, query_from_json
from .compiler import NQLCompiler, NQLResult
from .context import NQLContext
from .exceptions import NQLSyntaxError, UnknownEntityError
from .parser import parse_nql_text


def to_query(source) -> NQLQuery:
    if isinstance(source, NQLQuery):
        return source
    if isinstance(source, str):
        return parse_nql_text(source)
    if isinstance(source, dict):
        return query_from_json(source)
    raise NQLSyntaxError(f"Unsupported NQL source type: {type(source).__name__}")


def compile_nql(*, workspace_id, source, user_id=None, now=None) -> NQLResult:
    query = to_query(source)
    try:
        entity = SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=query.entity)
    except EntityNotFoundError as exc:
        raise UnknownEntityError(str(exc)) from exc
    if not entity.table_name:
        raise UnknownEntityError(f"Entity {query.entity!r} has no physical table yet")
    ctx = NQLContext(workspace_id=workspace_id, user_id=user_id, now=now)
    return NQLCompiler(entity, ctx).compile(query)


def _json_scalar(val):
    """Normalise a DB-native scalar to a JSON-serialisable value.

    PostgreSQL returns ``Decimal``/``UUID``/``datetime`` objects; SQLite returns plain
    str/float. Result rows feed reports, exports, snapshots, and workflow context — all
    of which JSON-encode — so they must be JSON-native and identical across backends.
    """
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def execute_nql(*, workspace_id, source, user_id=None, now=None) -> list[dict]:
    result = compile_nql(workspace_id=workspace_id, source=source, user_id=user_id, now=now)
    with connection.cursor() as cur:
        cur.execute(result.sql, result.params)
        columns = [c[0] for c in cur.description]
        return [{col: _json_scalar(val) for col, val in zip(columns, row, strict=False)}
                for row in cur.fetchall()]
