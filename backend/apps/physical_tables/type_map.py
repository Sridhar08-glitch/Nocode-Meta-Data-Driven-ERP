"""
Field-type → database column-type mapping.

Sridhar ERP field types map to PostgreSQL column types in production and to
SQLite-compatible equivalents in the test environment (SQLite is used by
config.settings.test to avoid needing a live Postgres server during CI).

Usage::

    from apps.physical_tables.type_map import get_column_type
    pg_type = get_column_type("decimal", config={"precision": 4}, vendor="postgresql")
    sl_type = get_column_type("decimal", config={"precision": 4}, vendor="sqlite")
"""
from __future__ import annotations

from django.db import connection

# ---------------------------------------------------------------------------
# PostgreSQL type map
# ---------------------------------------------------------------------------
_PG: dict[str, str] = {
    # Text
    "text": "VARCHAR(1000)",
    "textarea": "TEXT",
    "rich_text": "TEXT",
    "email": "VARCHAR(254)",
    "phone": "VARCHAR(50)",
    "url": "VARCHAR(2000)",
    "barcode": "VARCHAR(200)",
    # Numbers
    "integer": "BIGINT",
    "decimal": "NUMERIC(18,6)",
    "currency": "NUMERIC(18,4)",
    "percent": "NUMERIC(8,4)",
    "rating": "SMALLINT",
    "progress": "SMALLINT",
    "count": "BIGINT",
    "auto_number": "BIGINT",  # managed by sequence; not BIGSERIAL (column must allow ALTER)
    "duration": "BIGINT",  # stored as seconds
    # Date / time
    "date": "DATE",
    "datetime": "TIMESTAMPTZ",
    "time": "TIME",
    # Boolean
    "boolean": "BOOLEAN",
    # Selects (single → VARCHAR, multi → JSONB)
    "select": "VARCHAR(100)",
    "status": "VARCHAR(100)",
    "multi_select": "JSONB",
    # Relations
    "lookup": "UUID",
    "multi_lookup": "JSONB",
    "user": "UUID",
    "multi_user": "JSONB",
    # Files
    "file": "JSONB",
    "image": "JSONB",
    # Computed (stored result)
    "formula": "JSONB",
    "rollup": "JSONB",
    # System
    "created_at": "TIMESTAMPTZ",
    "updated_at": "TIMESTAMPTZ",
    "created_by": "UUID",
    "updated_by": "UUID",
    "uuid": "UUID",
    # Misc
    "json": "JSONB",
    "location": "JSONB",
}

# ---------------------------------------------------------------------------
# SQLite type map (tests only)
# ---------------------------------------------------------------------------
_SL: dict[str, str] = {
    "text": "TEXT",
    "textarea": "TEXT",
    "rich_text": "TEXT",
    "email": "TEXT",
    "phone": "TEXT",
    "url": "TEXT",
    "barcode": "TEXT",
    "integer": "INTEGER",
    "decimal": "REAL",
    "currency": "REAL",
    "percent": "REAL",
    "rating": "INTEGER",
    "progress": "INTEGER",
    "count": "INTEGER",
    "auto_number": "INTEGER",
    "duration": "INTEGER",
    "date": "TEXT",
    "datetime": "TEXT",
    "time": "TEXT",
    "boolean": "INTEGER",
    "select": "TEXT",
    "status": "TEXT",
    "multi_select": "TEXT",
    "lookup": "TEXT",
    "multi_lookup": "TEXT",
    "user": "TEXT",
    "multi_user": "TEXT",
    "file": "TEXT",
    "image": "TEXT",
    "formula": "TEXT",
    "rollup": "TEXT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
    "created_by": "TEXT",
    "updated_by": "TEXT",
    "uuid": "TEXT",
    "json": "TEXT",
    "location": "TEXT",
}


def get_column_type(
    field_type: str,
    config: dict | None = None,
    *,
    vendor: str | None = None,
) -> str:
    """Return the database column type string for a given Sridhar ERP field type.

    Args:
        field_type: One of the ``FIELD_TYPE_VALUES`` constants from ``apps.metadata``.
        config: Optional field-level config dict (used for precision overrides etc.).
        vendor: Database vendor string (``"postgresql"`` or ``"sqlite"``).
                Defaults to the vendor of the current DB connection.

    Returns:
        A SQL column type string suitable for use in DDL statements.
    """
    if vendor is None:
        vendor = connection.vendor

    if vendor == "sqlite":
        col_type = _SL.get(field_type, "TEXT")
    else:
        col_type = _PG.get(field_type, "TEXT")

        # Allow precision override for decimal-like types
        if config and field_type in ("decimal", "currency", "percent"):
            precision = config.get("precision")
            scale = config.get("scale")
            if isinstance(precision, int) and isinstance(scale, int):
                col_type = f"NUMERIC({precision},{scale})"
            elif isinstance(precision, int):
                col_type = f"NUMERIC({precision},2)"

    return col_type


def is_jsonb_type(field_type: str) -> bool:
    """Return True if this field type stores its value as JSONB / JSON TEXT."""
    return _PG.get(field_type, "TEXT").startswith("JSONB") or field_type in (
        "multi_select", "multi_lookup", "multi_user", "file", "image",
        "formula", "rollup", "json", "location",
    )
