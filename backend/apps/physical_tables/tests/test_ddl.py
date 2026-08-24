"""
Tests for apps.physical_tables.ddl — pure DDL string builders.

All tests work without a database connection because the builders are pure
functions.  The ``vendor`` keyword is passed explicitly so that the tests
produce deterministic output regardless of the test runner's DB backend.
"""
import pytest

from apps.physical_tables.ddl import (
    ColumnSpec,
    build_add_column_sql,
    build_create_index_sql,
    build_create_table_sql,
    build_drop_column_sql,
    build_drop_index_sql,
    build_drop_rls_sql,
    build_drop_table_sql,
    build_rename_column_sql,
    build_workspace_index_sql,
)

# ---------------------------------------------------------------------------
# ColumnSpec
# ---------------------------------------------------------------------------

class TestColumnSpec:
    def test_simple_text_column(self):
        col = ColumnSpec("first_name", "TEXT")
        sql = col.to_sql_fragment(vendor="postgresql")
        assert '"first_name" TEXT' in sql
        # nullable by default → no NOT NULL
        assert "NOT NULL" not in sql

    def test_not_null_column(self):
        col = ColumnSpec("email", "VARCHAR(254)", nullable=False)
        sql = col.to_sql_fragment(vendor="postgresql")
        assert "NOT NULL" in sql

    def test_default_column(self):
        col = ColumnSpec("created_at", "TIMESTAMPTZ", nullable=False, default="NOW()")
        sql = col.to_sql_fragment(vendor="postgresql")
        assert "DEFAULT NOW()" in sql

    def test_unique_column(self):
        col = ColumnSpec("code", "TEXT", unique=True)
        sql = col.to_sql_fragment(vendor="postgresql")
        assert "UNIQUE" in sql

    def test_primary_key_column(self):
        col = ColumnSpec("id", "UUID", nullable=False, primary_key=True)
        sql = col.to_sql_fragment(vendor="postgresql")
        assert "PRIMARY KEY" in sql
        # primary_key implies NOT NULL; UNIQUE should not appear separately
        assert "UNIQUE" not in sql

    def test_sqlite_column(self):
        col = ColumnSpec("id", "TEXT", nullable=False, primary_key=True)
        sql = col.to_sql_fragment(vendor="sqlite")
        assert '"id" TEXT NOT NULL PRIMARY KEY' in sql


# ---------------------------------------------------------------------------
# build_create_table_sql
# ---------------------------------------------------------------------------

class TestBuildCreateTableSql:
    def test_contains_create_table(self):
        sql = build_create_table_sql("my_table", vendor="postgresql")
        assert "CREATE TABLE" in sql
        assert '"my_table"' in sql

    def test_standard_columns_present_pg(self):
        sql = build_create_table_sql("demo_tbl", vendor="postgresql")
        for col in ("id", "workspace_id", "created_at", "updated_at",
                    "deleted_at", "created_by", "updated_by", "custom_data"):
            assert f'"{col}"' in sql

    def test_standard_columns_present_sqlite(self):
        sql = build_create_table_sql("demo_tbl", vendor="sqlite")
        for col in ("id", "workspace_id", "created_at", "updated_at", "custom_data"):
            assert f'"{col}"' in sql

    def test_extra_columns_appended(self):
        extra = [ColumnSpec("score", "BIGINT", nullable=True)]
        sql = build_create_table_sql("leads_tbl", extra_cols=extra, vendor="postgresql")
        assert '"score"' in sql

    def test_if_not_exists(self):
        sql = build_create_table_sql("safe_tbl", vendor="postgresql")
        assert "IF NOT EXISTS" in sql

    def test_unsafe_table_name_raises(self):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            build_create_table_sql("Robert'; DROP TABLE students;--", vendor="postgresql")

    def test_table_name_starting_with_digit_raises(self):
        with pytest.raises(ValueError):
            build_create_table_sql("1bad_name", vendor="postgresql")


# ---------------------------------------------------------------------------
# build_add_column_sql
# ---------------------------------------------------------------------------

class TestBuildAddColumnSql:
    def test_basic_add(self):
        col = ColumnSpec("phone", "VARCHAR(50)")
        sql = build_add_column_sql("contacts", col, vendor="postgresql")
        assert "ALTER TABLE" in sql
        assert '"contacts"' in sql
        assert "ADD COLUMN" in sql
        assert '"phone"' in sql
        assert "IF NOT EXISTS" in sql

    def test_add_not_null_with_default(self):
        col = ColumnSpec("is_active", "BOOLEAN", nullable=False, default="TRUE")
        sql = build_add_column_sql("employees", col, vendor="postgresql")
        assert "NOT NULL" in sql
        assert "DEFAULT TRUE" in sql

    def test_unsafe_column_raises(self):
        col = ColumnSpec("bad col", "TEXT")
        with pytest.raises(ValueError):
            build_add_column_sql("my_table", col, vendor="postgresql")


# ---------------------------------------------------------------------------
# build_drop_column_sql
# ---------------------------------------------------------------------------

class TestBuildDropColumnSql:
    def test_drop_column(self):
        sql = build_drop_column_sql("orders", "notes")
        assert "ALTER TABLE" in sql
        assert '"orders"' in sql
        assert "DROP COLUMN IF EXISTS" in sql
        assert '"notes"' in sql


# ---------------------------------------------------------------------------
# build_rename_column_sql
# ---------------------------------------------------------------------------

class TestBuildRenameColumnSql:
    def test_rename(self):
        sql = build_rename_column_sql("contacts", "old_name", "new_name")
        assert "RENAME COLUMN" in sql
        assert '"old_name"' in sql
        assert '"new_name"' in sql


# ---------------------------------------------------------------------------
# build_create_index_sql
# ---------------------------------------------------------------------------

class TestBuildCreateIndexSql:
    def test_non_unique_index(self):
        sql = build_create_index_sql("leads", "status")
        assert "CREATE INDEX" in sql
        assert "UNIQUE" not in sql
        assert '"leads"' in sql
        assert '"status"' in sql

    def test_unique_index(self):
        sql = build_create_index_sql("contacts", "email", unique=True)
        assert "CREATE UNIQUE INDEX" in sql

    def test_custom_index_name(self):
        sql = build_create_index_sql("tbl", "col", index_name="my_special_idx")
        assert '"my_special_idx"' in sql

    def test_if_not_exists(self):
        sql = build_create_index_sql("tbl", "col")
        assert "IF NOT EXISTS" in sql


# ---------------------------------------------------------------------------
# build_drop_index_sql
# ---------------------------------------------------------------------------

class TestBuildDropIndexSql:
    def test_drop_index(self):
        sql = build_drop_index_sql("ix_my_table_col")
        assert "DROP INDEX" in sql
        assert '"ix_my_table_col"' in sql
        assert "IF EXISTS" in sql


# ---------------------------------------------------------------------------
# build_workspace_index_sql
# ---------------------------------------------------------------------------

class TestBuildWorkspaceIndexSql:
    def test_workspace_index(self):
        sql = build_workspace_index_sql("nexus_t_abc12345_lead")
        assert '"workspace_id"' in sql
        assert "nexus_t_abc12345_lead" in sql


# ---------------------------------------------------------------------------
# build_rls_sql / build_drop_rls_sql
# ---------------------------------------------------------------------------

class TestRlsSql:
    def test_rls_returns_statements_on_pg(self, settings, db):
        """On a real DB we can only test the string content, not connection.vendor."""
        from unittest.mock import patch

        from apps.physical_tables.ddl import build_rls_sql
        with patch("apps.physical_tables.ddl.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            stmts = build_rls_sql("my_entity_table")
        assert len(stmts) == 3
        joined = " ".join(stmts)
        assert "ENABLE ROW LEVEL SECURITY" in joined
        assert "CREATE POLICY" in joined
        assert "app.workspace_id" in joined

    def test_rls_returns_empty_on_sqlite(self):
        from unittest.mock import patch

        from apps.physical_tables.ddl import build_rls_sql
        with patch("apps.physical_tables.ddl.connection") as mock_conn:
            mock_conn.vendor = "sqlite"
            stmts = build_rls_sql("my_entity_table")
        assert stmts == []

    def test_drop_rls_pg(self):
        from unittest.mock import patch
        with patch("apps.physical_tables.ddl.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            stmts = build_drop_rls_sql("my_tbl")
        assert any("DROP POLICY" in s for s in stmts)
        assert any("DISABLE ROW LEVEL SECURITY" in s for s in stmts)


# ---------------------------------------------------------------------------
# build_drop_table_sql
# ---------------------------------------------------------------------------

class TestBuildDropTableSql:
    def test_drop_table(self):
        sql = build_drop_table_sql("nexus_t_abc12345_lead")
        assert "DROP TABLE IF EXISTS" in sql
        assert "CASCADE" in sql
        assert '"nexus_t_abc12345_lead"' in sql
