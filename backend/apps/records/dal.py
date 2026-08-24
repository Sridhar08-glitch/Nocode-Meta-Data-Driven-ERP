"""
Physical-table data access for dynamic records.

Writes/reads rows on the generated entity table, splitting values between promoted
typed columns and the ``custom_data`` JSONB overflow, vendor-aware (PostgreSQL
JSONB / SQLite TEXT). All values are bound parameters — never interpolated.

This is the write counterpart to the NQL read compiler.
"""
from __future__ import annotations

import json
import uuid as _uuid
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from apps.nql.exceptions import NQLValueError, UnknownFieldError

_NUMERIC = {"integer", "number", "decimal", "currency", "percentage", "rating",
            "auto_number", "formula", "rollup"}
_UUIDISH = {"lookup", "user", "uuid"}
_DATETIME = {"date", "datetime", "time"}
_SYSTEM_OUT = ["id", "created_at", "updated_at", "created_by", "updated_by", "deleted_at"]


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


class FieldMap:
    def __init__(self, entity):
        self.entity = entity
        self.fields = {fd.slug: fd for fd in entity.fields.filter(is_deleted=False)}

    def coerce(self, slug, value):
        cat = _category(self.fields[slug].field_type)
        if value is None:
            return None
        # An empty string is "no value" for typed columns. Binding "" to a
        # uuid/datetime/numeric/boolean column is invalid on PostgreSQL
        # (e.g. ''::uuid -> DataError); SQLite's loose typing hides it. Treat
        # it as NULL. Text columns keep "" (a legitimate empty string).
        if value == "" and cat != "text":
            return None
        try:
            if cat == "numeric":
                return float(value) if "." in str(value) else int(value)
            if cat == "boolean":
                b = str(value).lower() in ("true", "1", "yes", "t")
                return b if connection.vendor == "postgresql" else int(b)
            return str(value)
        except (TypeError, ValueError) as exc:
            raise NQLValueError(f"Bad value for {slug!r}") from exc

    def split(self, data: dict, *, partial: bool):
        """Validate *data* and split into (promoted_columns, overflow_dict)."""
        for key in data:
            if key not in self.fields:
                raise UnknownFieldError(f"Unknown field {key!r} on {self.entity.slug!r}")
        if not partial:
            for slug, fd in self.fields.items():
                if fd.is_required and not fd.is_system and data.get(slug) in (None, ""):
                    raise NQLValueError(f"Field {slug!r} is required")
        promoted, overflow = {}, {}
        for slug, raw in data.items():
            fd = self.fields[slug]
            val = self.coerce(slug, raw)
            if fd.is_promoted:
                promoted[fd.column_name or slug] = (val, _category(fd.field_type))
            else:
                overflow[slug] = val
        return promoted, overflow


def _ph_uuid():
    return "%s::uuid" if connection.vendor == "postgresql" else "%s"


def _ph_jsonb():
    return "%s::jsonb" if connection.vendor == "postgresql" else "%s"


def _col_ph(category):
    if connection.vendor != "postgresql":
        return "%s"
    if category == "uuid":
        return "%s::uuid"
    if category == "datetime":
        return "%s::timestamptz"
    return "%s"


def insert_row(entity, fmap: FieldMap, promoted: dict, overflow: dict, *, actor_id,
               record_id=None, event_version: int = 1) -> str:
    table = entity.table_name
    rid = str(record_id) if record_id else str(_uuid.uuid4())
    cols = ['"id"', '"workspace_id"', '"created_by"', '"updated_by"', '"custom_data"', '"_event_version"']
    phs = [_ph_uuid(), _ph_uuid(), _ph_uuid(), _ph_uuid(), _ph_jsonb(), "%s"]
    params = [rid, str(entity.workspace_id), str(actor_id) if actor_id else None,
              str(actor_id) if actor_id else None, json.dumps(overflow), event_version]
    for col, (val, cat) in promoted.items():
        cols.append(f'"{col}"')
        phs.append(_col_ph(cat))
        params.append(val)
    sql = f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(phs)})'
    with connection.cursor() as cur:
        cur.execute(sql, params)
    return rid


def update_row(entity, fmap: FieldMap, record_id, promoted: dict, overflow: dict, *, actor_id,
               event_version: int | None = None) -> None:
    table = entity.table_name
    sets, params = [], []
    if event_version is not None:
        sets.append('"_event_version" = %s')
        params.append(event_version)
    for col, (val, cat) in promoted.items():
        sets.append(f'"{col}" = {_col_ph(cat)}')
        params.append(val)
    if overflow:
        # merge overflow into existing custom_data
        existing = get_row(entity, fmap, record_id) or {}
        merged = {k: existing.get(k) for k in fmap.fields if not fmap.fields[k].is_promoted}
        merged.update(overflow)
        sets.append(f'"custom_data" = {_ph_jsonb()}')
        params.append(json.dumps({k: v for k, v in merged.items() if v is not None}))
    sets.append(f'"updated_by" = {_ph_uuid()}')
    params.append(str(actor_id) if actor_id else None)
    now = "NOW()" if connection.vendor == "postgresql" else "datetime('now')"
    sets.append(f'"updated_at" = {now}')          # literal — no bound param
    params.append(str(record_id))
    sql = (f'UPDATE "{table}" SET {", ".join(sets)} '
           f'WHERE "id" = {_ph_uuid()} AND "deleted_at" IS NULL')
    with connection.cursor() as cur:
        cur.execute(sql, params)


def soft_delete_row(entity, record_id, *, actor_id) -> int:
    table = entity.table_name
    now = "NOW()" if connection.vendor == "postgresql" else "datetime('now')"
    sql = (f'UPDATE "{table}" SET "deleted_at" = {now}, "deleted_by" = {_ph_uuid()} '
           f'WHERE "id" = {_ph_uuid()} AND "deleted_at" IS NULL')
    with connection.cursor() as cur:
        cur.execute(sql, [str(actor_id) if actor_id else None, str(record_id)])
        return cur.rowcount


def restore_row(entity, record_id) -> int:
    table = entity.table_name
    sql = (f'UPDATE "{table}" SET "deleted_at" = NULL, "deleted_by" = NULL '
           f'WHERE "id" = {_ph_uuid()} AND "deleted_at" IS NOT NULL')
    with connection.cursor() as cur:
        cur.execute(sql, [str(record_id)])
        return cur.rowcount


def get_row(entity, fmap: FieldMap, record_id, *, include_deleted=False) -> dict | None:
    table = entity.table_name
    extra = "" if include_deleted else ' AND "deleted_at" IS NULL'
    sql = (f'SELECT * FROM "{table}" WHERE "id" = {_ph_uuid()} '
           f'AND "workspace_id" = {_ph_uuid()}{extra}')
    with connection.cursor() as cur:
        cur.execute(sql, [str(record_id), str(entity.workspace_id)])
        row = cur.fetchone()
        if row is None:
            return None
        cols = [c[0] for c in cur.description]
    return row_to_record(dict(zip(cols, row, strict=False)), fmap)


def _json_scalar(val):
    """Coerce a DB-native scalar to a JSON-serialisable value.

    PostgreSQL returns ``Decimal``/``UUID``/``datetime`` objects for typed columns;
    SQLite returns plain str/float. Normalising here keeps record dicts JSON-safe and
    identical across both backends (they flow into JSONField writes and REST output).
    """
    if isinstance(val, _uuid.UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def row_to_record(raw: dict, fmap: FieldMap) -> dict:
    """Flatten a physical-table row into a record dict keyed by field slug."""
    custom = raw.get("custom_data")
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except (TypeError, ValueError):
            custom = {}
    custom = custom or {}
    out = {}
    for key in _SYSTEM_OUT:
        out[key] = _json_scalar(raw.get(key))
    for slug, fd in fmap.fields.items():
        if fd.is_promoted:
            val = _json_scalar(raw.get(fd.column_name or slug))
            out[slug] = _format_auto_number(fd, val) if fd.field_type == "auto_number" else val
        else:
            out[slug] = custom.get(slug)
    return out


def _format_auto_number(fd, value):
    """Render an auto_number integer as its display string using the field's
    ``prefix``/``suffix``/``padding`` config → e.g. 1 → ``APP-000001``."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    cfg = fd.config or {}
    pad = int(cfg.get("padding", 0) or 0)
    return f"{cfg.get('prefix', '')}{n:0{pad}d}{cfg.get('suffix', '')}"


def get_event_version(entity, record_id):
    """Return the row's ``_event_version`` (int), or None if the row is absent."""
    with connection.cursor() as cur:
        cur.execute(f'SELECT "_event_version" FROM "{entity.table_name}" WHERE "id" = {_ph_uuid()}',
                    [str(record_id)])
        row = cur.fetchone()
    return None if row is None else int(row[0])


def set_deleted(entity, record_id, *, deleted: bool, event_version: int, actor_id=None) -> None:
    """Projection helper: set/clear soft-delete + advance ``_event_version`` for any row."""
    table = entity.table_name
    if deleted:
        now = "NOW()" if connection.vendor == "postgresql" else "datetime('now')"
        sql = (f'UPDATE "{table}" SET "deleted_at" = {now}, "deleted_by" = {_ph_uuid()}, '
               f'"_event_version" = %s WHERE "id" = {_ph_uuid()}')
        params = [str(actor_id) if actor_id else None, event_version, str(record_id)]
    else:
        sql = (f'UPDATE "{table}" SET "deleted_at" = NULL, "deleted_by" = NULL, '
               f'"_event_version" = %s WHERE "id" = {_ph_uuid()}')
        params = [event_version, str(record_id)]
    with connection.cursor() as cur:
        cur.execute(sql, params)


def now_iso():
    return timezone.now().isoformat()
