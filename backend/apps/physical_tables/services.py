"""
PhysicalTableGenerator
======================
Creates and manages real database tables for dynamic Nexus entity definitions.

Every entity whose ``has_physical_table`` flag is True gets a dedicated
database table whose lifecycle is managed entirely here:

    create_table   →  CREATE TABLE + index on workspace_id + RLS (PG only)
    add_column     →  ALTER TABLE ADD COLUMN (+ optional index)
    drop_column    →  ALTER TABLE DROP COLUMN (+ drop index if any)
    rename_column  →  ALTER TABLE RENAME COLUMN
    drop_table     →  DROP TABLE CASCADE + remove RLS + clear EntityPhysicalTable

On PostgreSQL every generated table carries a Row Level Security policy so that
rows are invisible unless ``app.workspace_id`` matches — enforcement happens at
the database layer independent of ORM filters.

On SQLite (test environment):
    - RLS statements are skipped automatically (``build_rls_sql`` returns [])
    - Column types use the SQLite equivalents from ``type_map``
    - All structural operations (create / add / drop) still execute real SQL
      so the service is fully exercised in tests
    - DROP COLUMN is also skipped (not supported in old SQLite)

Table naming convention::

    nexus_t_{ws_hex8}_{entity_slug}

    where ws_hex8 = workspace_id.hex[:8]   e.g. "a1b2c3d4"

All public methods update the ``EntityPhysicalTable`` tracker row in the same
transaction as the DDL, so the metadata and the physical schema stay in sync.
"""
from __future__ import annotations

import logging
import uuid

from django.db import connection, transaction

from apps.metadata.models import EntityDefinition, EntityPhysicalTable, FieldDefinition
from apps.physical_tables.ddl import (
    ColumnSpec,
    build_add_column_sql,
    build_change_column_type_sql,
    build_create_index_sql,
    build_create_table_sql,
    build_drop_column_sql,
    build_drop_index_sql,
    build_drop_rls_sql,
    build_drop_table_sql,
    build_rename_column_sql,
    build_rls_sql,
    build_workspace_index_sql,
)
from apps.physical_tables.type_map import get_column_type

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_postgres() -> bool:
    return connection.vendor == "postgresql"


def build_table_name(workspace_id: uuid.UUID, entity_slug: str) -> str:
    """Return the deterministic table name for a workspace + entity combination.

    The result always matches ``^[a-z][a-z0-9_]{0,62}$`` so it is safe to pass
    to the DDL builders.
    """
    ws_hex8 = workspace_id.hex[:8]
    slug = entity_slug[:45].replace("-", "_")
    return f"nexus_t_{ws_hex8}_{slug}"


def _col_spec_from_field(field_def: FieldDefinition) -> ColumnSpec:
    """Translate a FieldDefinition into a ColumnSpec for DDL generation."""
    col_type = get_column_type(
        field_def.field_type,
        config=field_def.config,
        vendor=connection.vendor,
    )
    default: str | None = None
    if field_def.default_value is not None:
        val = field_def.default_value
        if isinstance(val, str):
            escaped = val.replace("'", "''")
            default = f"'{escaped}'"
        elif isinstance(val, bool):
            default = "TRUE" if val else "FALSE"
        elif isinstance(val, int | float):
            default = str(val)

    col_name = field_def.column_name or field_def.slug
    return ColumnSpec(
        name=col_name,
        col_type=col_type,
        nullable=not field_def.is_required,
        default=default,
        unique=field_def.is_unique,
    )


# ---------------------------------------------------------------------------
# Generator service
# ---------------------------------------------------------------------------

class PhysicalTableGenerator:
    """Service class that drives all DDL for Nexus-generated entity tables."""

    @staticmethod
    def create_table(entity: EntityDefinition) -> EntityPhysicalTable:
        """Create a physical table for *entity* and register it in
        ``EntityPhysicalTable``.

        Promoted fields (``is_promoted=True``) become real columns.

        Raises:
            ValueError: if the entity already has a physical table.
        """
        if entity.has_physical_table:
            raise ValueError(
                f"Entity {entity.slug!r} already has a physical table: "
                f"{entity.table_name!r}"
            )

        table_name = build_table_name(entity.workspace_id, entity.slug)
        promoted = list(entity.fields.filter(is_promoted=True).order_by("order"))
        extra_cols = [_col_spec_from_field(f) for f in promoted]

        stmts: list[str] = [
            build_create_table_sql(table_name, extra_cols),
            build_workspace_index_sql(table_name),
        ]

        # Indexes for filterable/sortable promoted fields
        for fd in promoted:
            if fd.has_index or fd.is_filterable or fd.is_sortable:
                col_name = fd.column_name or fd.slug
                stmts.append(
                    build_create_index_sql(
                        table_name,
                        col_name,
                        unique=fd.is_unique,
                    )
                )

        # RLS (PostgreSQL only — no-op on SQLite)
        stmts.extend(build_rls_sql(table_name))

        with transaction.atomic():
            PhysicalTableGenerator._exec_ddl(stmts)

            entity.table_name = table_name
            entity.has_physical_table = True
            entity.save(update_fields=["table_name", "has_physical_table"])

            tracker = EntityPhysicalTable.objects.create(
                entity=entity,
                workspace_id=entity.workspace_id,
                table_name=table_name,
                status="ready",
                promoted_columns=[
                    {
                        "slug": fd.slug,
                        "column_name": fd.column_name or fd.slug,
                        "pg_type": get_column_type(
                            fd.field_type, config=fd.config, vendor=connection.vendor
                        ),
                        "field_type": fd.field_type,
                    }
                    for fd in promoted
                ],
            )

        log.info("Created physical table %r for entity %r", table_name, entity.slug)
        return tracker

    @staticmethod
    def add_column(
        entity: EntityDefinition,
        field_def: FieldDefinition,
    ) -> None:
        """Add a column for *field_def* to the entity's physical table.

        Also creates an index if appropriate. Marks the field as promoted and
        updates the ``EntityPhysicalTable.promoted_columns`` list.
        """
        table_name = entity.table_name
        if not table_name:
            raise ValueError(f"Entity {entity.slug!r} has no physical table yet")

        col = _col_spec_from_field(field_def)
        stmts = [build_add_column_sql(table_name, col)]

        if field_def.has_index or field_def.is_filterable or field_def.is_sortable:
            stmts.append(
                build_create_index_sql(
                    table_name,
                    col.name,
                    unique=field_def.is_unique,
                )
            )

        with transaction.atomic():
            PhysicalTableGenerator._exec_ddl(stmts)

            field_def.is_promoted = True
            field_def.column_name = col.name
            field_def.save(update_fields=["is_promoted", "column_name"])

            try:
                tracker = entity.physical_table
                cols = list(tracker.promoted_columns or [])
                cols.append({
                    "slug": field_def.slug,
                    "column_name": col.name,
                    "pg_type": get_column_type(
                        field_def.field_type,
                        config=field_def.config,
                        vendor=connection.vendor,
                    ),
                    "field_type": field_def.field_type,
                })
                tracker.promoted_columns = cols
                tracker.save(update_fields=["promoted_columns"])
            except EntityPhysicalTable.DoesNotExist:
                pass

        log.info("Added column %r to table %r", col.name, table_name)

    @staticmethod
    def drop_column(
        entity: EntityDefinition,
        field_def: FieldDefinition,
    ) -> None:
        """Drop the promoted column for *field_def* from the entity's table.

        Drops the associated index first. Updates the tracker and marks the
        field as non-promoted.

        Note: SQLite does not support ``DROP COLUMN`` so on SQLite only the
        metadata update is performed (the column remains in the DB but is
        treated as non-promoted).
        """
        table_name = entity.table_name
        if not table_name:
            raise ValueError(f"Entity {entity.slug!r} has no physical table yet")

        col_name = field_def.column_name or field_def.slug
        stmts: list[str] = []

        if field_def.is_unique:
            stmts.append(build_drop_index_sql(f"uq_{table_name}_{col_name}"))
        elif field_def.has_index or field_def.is_filterable or field_def.is_sortable:
            stmts.append(build_drop_index_sql(f"ix_{table_name}_{col_name}"))

        if _is_postgres():
            stmts.append(build_drop_column_sql(table_name, col_name))

        with transaction.atomic():
            if stmts:
                PhysicalTableGenerator._exec_ddl(stmts)

            field_def.is_promoted = False
            field_def.column_name = ""
            field_def.save(update_fields=["is_promoted", "column_name"])

            try:
                tracker = entity.physical_table
                tracker.promoted_columns = [
                    c for c in tracker.promoted_columns
                    if c.get("slug") != field_def.slug
                ]
                tracker.save(update_fields=["promoted_columns"])
            except EntityPhysicalTable.DoesNotExist:
                pass

        log.info("Dropped column %r from table %r", col_name, table_name)

    @staticmethod
    def rename_column(
        entity: EntityDefinition,
        field_def: FieldDefinition,
        new_column_name: str,
    ) -> None:
        """Rename a promoted column.

        No-op DDL on SQLite; metadata update always runs.
        """
        table_name = entity.table_name
        if not table_name:
            raise ValueError(f"Entity {entity.slug!r} has no physical table yet")

        old_name = field_def.column_name or field_def.slug

        with transaction.atomic():
            if _is_postgres():
                PhysicalTableGenerator._exec_ddl([
                    build_rename_column_sql(table_name, old_name, new_column_name)
                ])

            field_def.column_name = new_column_name
            field_def.save(update_fields=["column_name"])

            try:
                tracker = entity.physical_table
                for col in tracker.promoted_columns:
                    if col.get("slug") == field_def.slug:
                        col["column_name"] = new_column_name
                tracker.save(update_fields=["promoted_columns"])
            except EntityPhysicalTable.DoesNotExist:
                pass

        log.info(
            "Renamed column %r -> %r in table %r", old_name, new_column_name, table_name
        )

    @staticmethod
    def change_column_type(
        entity: EntityDefinition,
        field_def: FieldDefinition,
        new_field_type: str,
        new_config: dict | None = None,
    ) -> None:
        """Change the column type for a promoted field (PostgreSQL only).

        The ``USING`` clause attempts a direct cast; callers must ensure data
        compatibility before calling this method.
        """
        table_name = entity.table_name
        if not table_name:
            raise ValueError(f"Entity {entity.slug!r} has no physical table yet")

        col_name = field_def.column_name or field_def.slug
        new_pg_type = get_column_type(
            new_field_type, config=new_config or {}, vendor=connection.vendor
        )

        with transaction.atomic():
            if _is_postgres():
                PhysicalTableGenerator._exec_ddl([
                    build_change_column_type_sql(table_name, col_name, new_pg_type)
                ])

            field_def.field_type = new_field_type
            if new_config is not None:
                field_def.config = new_config
            field_def.save(update_fields=["field_type", "config"])

            try:
                tracker = entity.physical_table
                for col in tracker.promoted_columns:
                    if col.get("slug") == field_def.slug:
                        col["pg_type"] = new_pg_type
                        col["field_type"] = new_field_type
                tracker.save(update_fields=["promoted_columns"])
            except EntityPhysicalTable.DoesNotExist:
                pass

    @staticmethod
    def drop_table(entity: EntityDefinition) -> None:
        """Drop the physical table and remove all associated metadata.

        Drops RLS policies first (PostgreSQL only), then ``DROP TABLE CASCADE``.
        Resets ``entity.has_physical_table`` and deletes the tracker row.
        """
        table_name = entity.table_name
        if not table_name:
            raise ValueError(f"Entity {entity.slug!r} has no physical table yet")

        stmts: list[str] = []
        stmts.extend(build_drop_rls_sql(table_name))
        stmts.append(build_drop_table_sql(table_name, vendor=connection.vendor))

        with transaction.atomic():
            PhysicalTableGenerator._exec_ddl(stmts)

            EntityPhysicalTable.objects.filter(entity=entity).delete()

            entity.table_name = ""
            entity.has_physical_table = False
            entity.save(update_fields=["table_name", "has_physical_table"])

        log.info("Dropped physical table %r", table_name)

    @staticmethod
    def table_exists(table_name: str) -> bool:
        """Return True if *table_name* exists in the current database.

        Uses direct SQL rather than Django's introspection layer so that tables
        created within a pytest-django test transaction are visible (the
        introspection layer queries system catalogs in a way that can miss
        tables created in the same non-autocommit transaction context).
        """
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute(
                    "SELECT COUNT(*) FROM sqlite_master"
                    " WHERE type='table' AND name=%s",
                    [table_name],
                )
                return cursor.fetchone()[0] > 0
            # PostgreSQL — information_schema is visible within the same
            # transaction, so this works correctly in both prod and tests.
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables"
                " WHERE table_schema = 'public' AND table_name = %s",
                [table_name],
            )
            return cursor.fetchone()[0] > 0

    @staticmethod
    def get_table_columns(table_name: str) -> list[dict]:
        """Return the current column list for *table_name* via DB introspection.

           Each dict has keys: ``name``, ``type``, ``nullable``.
        Returns an empty list if the table does not exist.

        Uses direct SQL on SQLite (``PRAGMA table_info``) so that columns added
        within a pytest-django test transaction are visible -- Django's
        ``get_table_description`` can miss them in the same way as
        ``table_names``.  On PostgreSQL the standard introspection path is used.
        """
        try:
            with connection.cursor() as cursor:
                if connection.vendor == "sqlite":
                    # PRAGMA cannot be parameterized; table_name is always
                    # produced by build_table_name() which enforces the safe
                    # ^[a-z][a-z0-9_]{0,62}$ pattern.
                    cursor.execute(f'PRAGMA table_info("{table_name}")')
                    rows = cursor.fetchall()
                    # PRAGMA table_info columns:
                    #   0=cid, 1=name, 2=type, 3=notnull, 4=dflt_value, 5=pk
                    return [
                        {
                            "name": row[1],
                            "type": row[2],
                            "nullable": not bool(row[3]),
                        }
                        for row in rows
                    ]
                cols = connection.introspection.get_table_description(
                    cursor, table_name
                )
            return [
                {
                    "name": c.name,
                    "type": c.type_code,
                    "nullable": c.null_ok,
                }
                for c in cols
            ]
        except Exception:
            return []

    @staticmethod
    def _exec_ddl(statements: list[str]) -> None:
        """Execute a list of DDL statements using a raw cursor."""
        with connection.cursor() as cursor:
            for sql in statements:
                if sql.strip():
                    log.debug("DDL: %s", sql)
                    cursor.execute(sql)
