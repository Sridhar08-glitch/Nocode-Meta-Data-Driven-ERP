"""
Pure DDL string builders.

These functions return SQL strings only — they never execute anything.
Execution lives in :mod:`apps.physical_tables.services`.

All functions accept a ``vendor`` keyword so they can emit SQLite-compatible
DDL in the test environment without hitting a live PostgreSQL server.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from django.db import connection

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ColumnSpec:
    """Represents a single column in a generated table."""
    name: str
    col_type: str
    nullable: bool = True
    default: str | None = None  # raw SQL expression, e.g. "NOW()" or "'{}'"
    unique: bool = False
    primary_key: bool = False

    def to_sql_fragment(self, *, vendor: str = "postgresql") -> str:
        parts: list[str] = [f'"{self.name}" {self.col_type}']
        if self.primary_key:
            parts.append("NOT NULL PRIMARY KEY")
        elif not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Standard columns every generated table carries
# ---------------------------------------------------------------------------

def _standard_columns(*, vendor: str = "postgresql") -> list[ColumnSpec]:
    """Return the fixed columns present on every Nexus-generated table."""
    if vendor == "sqlite":
        return [
            ColumnSpec("id", "TEXT", nullable=False, primary_key=True),
            ColumnSpec("workspace_id", "TEXT", nullable=False),
            ColumnSpec("created_at", "TEXT", nullable=False, default="(datetime('now'))"),
            ColumnSpec("updated_at", "TEXT", nullable=False, default="(datetime('now'))"),
            ColumnSpec("deleted_at", "TEXT"),
            ColumnSpec("created_by", "TEXT"),
            ColumnSpec("updated_by", "TEXT"),
            ColumnSpec("deleted_by", "TEXT"),
            ColumnSpec("custom_data", "TEXT", nullable=False, default="'{}'"),
            # Last domain event applied to this row — enables idempotent projection (§5.2A).
            ColumnSpec("_event_version", "INTEGER", nullable=False, default="0"),
        ]
    return [
        ColumnSpec("id", "UUID", nullable=False, default="gen_random_uuid()", primary_key=True),
        ColumnSpec("workspace_id", "UUID", nullable=False),
        ColumnSpec("created_at", "TIMESTAMPTZ", nullable=False, default="NOW()"),
        ColumnSpec("updated_at", "TIMESTAMPTZ", nullable=False, default="NOW()"),
        ColumnSpec("deleted_at", "TIMESTAMPTZ"),
        ColumnSpec("created_by", "UUID"),
        ColumnSpec("updated_by", "UUID"),
        ColumnSpec("deleted_by", "UUID"),
        ColumnSpec("custom_data", "JSONB", nullable=False, default="'{}'"),
        # Last domain event applied to this row — enables idempotent projection (§5.2A).
        ColumnSpec("_event_version", "BIGINT", nullable=False, default="0"),
    ]


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_SAFE_IDENT = re.compile(r'^[a-z][a-z0-9_]{0,62}$')


def _assert_safe(name: str, label: str = "name") -> None:
    """Raise ValueError if *name* is not a safe SQL identifier."""
    if not _SAFE_IDENT.match(name):
        raise ValueError(
            f"Unsafe SQL identifier for {label}: {name!r}. "
            "Must match ^[a-z][a-z0-9_]{0,62}$"
        )


# ---------------------------------------------------------------------------
# DDL builders
# ---------------------------------------------------------------------------

def build_create_table_sql(
    table_name: str,
    extra_cols: list[ColumnSpec] | None = None,
    *,
    vendor: str | None = None,
) -> str:
    """Return a ``CREATE TABLE`` statement.

    Args:
        table_name: Target table name (validated).
        extra_cols: Promoted field columns to append after standard columns.
        vendor: DB vendor override; defaults to current connection vendor.

    Returns:
        Full ``CREATE TABLE IF NOT EXISTS ...`` SQL string.
    """
    if vendor is None:
        vendor = connection.vendor
    _assert_safe(table_name, "table_name")

    cols = _standard_columns(vendor=vendor) + (extra_cols or [])
    col_defs = ",\n    ".join(c.to_sql_fragment(vendor=vendor) for c in cols)

    return (
        f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n'
        f"    {col_defs}\n"
        f");"
    )


def build_add_column_sql(
    table_name: str,
    col: ColumnSpec,
    *,
    vendor: str | None = None,
) -> str:
    """Return an ``ALTER TABLE … ADD COLUMN`` statement.

    SQLite does not support ``IF NOT EXISTS`` in ``ADD COLUMN``, so that
    clause is omitted when *vendor* is ``"sqlite"``.
    """
    if vendor is None:
        vendor = connection.vendor
    _assert_safe(table_name, "table_name")
    _assert_safe(col.name, "column_name")
    fragment = col.to_sql_fragment(vendor=vendor)
    if vendor == "sqlite":
        return f'ALTER TABLE "{table_name}" ADD COLUMN {fragment};'
    return f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS {fragment};'


def build_drop_column_sql(table_name: str, column_name: str) -> str:
    """Return an ``ALTER TABLE … DROP COLUMN`` statement."""
    _assert_safe(table_name, "table_name")
    _assert_safe(column_name, "column_name")
    return f'ALTER TABLE "{table_name}" DROP COLUMN IF EXISTS "{column_name}";'


def build_rename_column_sql(
    table_name: str,
    old_name: str,
    new_name: str,
) -> str:
    """Return an ``ALTER TABLE … RENAME COLUMN`` statement."""
    _assert_safe(table_name, "table_name")
    _assert_safe(old_name, "old_name")
    _assert_safe(new_name, "new_name")
    return (
        f'ALTER TABLE "{table_name}" '
        f'RENAME COLUMN "{old_name}" TO "{new_name}";'
    )


def build_change_column_type_sql(
    table_name: str,
    column_name: str,
    new_type: str,
) -> str:
    """Return an ``ALTER TABLE … ALTER COLUMN … TYPE`` statement (PostgreSQL only)."""
    _assert_safe(table_name, "table_name")
    _assert_safe(column_name, "column_name")
    return (
        f'ALTER TABLE "{table_name}" '
        f'ALTER COLUMN "{column_name}" TYPE {new_type} '
        f'USING "{column_name}"::{new_type};'
    )


def build_create_index_sql(
    table_name: str,
    column_name: str,
    *,
    unique: bool = False,
    index_name: str | None = None,
) -> str:
    """Return a ``CREATE INDEX`` statement."""
    _assert_safe(table_name, "table_name")
    _assert_safe(column_name, "column_name")
    if index_name is None:
        prefix = "uq" if unique else "ix"
        index_name = f"{prefix}_{table_name}_{column_name}"
    _assert_safe(index_name, "index_name")
    unique_kw = "UNIQUE " if unique else ""
    return (
        f'CREATE {unique_kw}INDEX IF NOT EXISTS "{index_name}" '
        f'ON "{table_name}" ("{column_name}");'
    )


def build_drop_index_sql(index_name: str) -> str:
    """Return a ``DROP INDEX`` statement."""
    _assert_safe(index_name, "index_name")
    return f'DROP INDEX IF EXISTS "{index_name}";'


def build_workspace_index_sql(table_name: str) -> str:
    """Return a ``CREATE INDEX`` for ``workspace_id`` — always added on table creation."""
    _assert_safe(table_name, "table_name")
    idx = f"ix_{table_name}_workspace_id"
    return (
        f'CREATE INDEX IF NOT EXISTS "{idx}" '
        f'ON "{table_name}" ("workspace_id");'
    )


def build_rls_sql(table_name: str) -> list[str]:
    """Return the list of SQL statements that enable and configure RLS.

    Returns an empty list on SQLite (RLS is a PostgreSQL-only feature).
    """
    if connection.vendor == "sqlite":
        return []

    _assert_safe(table_name, "table_name")
    policy_name = f"rls_{table_name}_workspace"
    return [
        f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY;',
        f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY;',
        (
            f'CREATE POLICY "{policy_name}" ON "{table_name}" '
            f"USING (workspace_id = "
            f"NULLIF(current_setting('app.workspace_id', TRUE), '')::UUID);"
        ),
    ]


def build_drop_rls_sql(table_name: str) -> list[str]:
    """Return statements to drop the workspace RLS policy."""
    if connection.vendor == "sqlite":
        return []
    _assert_safe(table_name, "table_name")
    policy_name = f"rls_{table_name}_workspace"
    return [
        f'DROP POLICY IF EXISTS "{policy_name}" ON "{table_name}";',
        f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY;',
    ]


def build_drop_table_sql(table_name: str, *, vendor: str = "postgresql") -> str:
    """Return a ``DROP TABLE IF EXISTS`` statement.

    The default vendor is ``"postgresql"`` so that callers who only need the
    SQL string (e.g. tests, migration preview) always get the full CASCADE
    form.  Callers that actually *execute* the statement should pass
    ``vendor=connection.vendor`` explicitly so SQLite-incompatible syntax is
    avoided when running under the test database.
    """
    _assert_safe(table_name, "table_name")
    if vendor == "sqlite":
        return f'DROP TABLE IF EXISTS "{table_name}";'
    return f'DROP TABLE IF EXISTS "{table_name}" CASCADE;'
