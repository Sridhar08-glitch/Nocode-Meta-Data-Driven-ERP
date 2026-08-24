"""
Integration tests for PhysicalTableGenerator.

These tests run against the real SQLite test database so every DDL statement
is actually executed.  This verifies end-to-end behaviour: table creation,
column addition, tracker update, table drop, and introspection.

RLS-specific assertions are skipped automatically (connection.vendor == "sqlite"
means ``build_rls_sql`` returns [] and ``drop_column`` skips the ALTER).
"""
import uuid

import pytest

from apps.metadata.models import EntityDefinition, EntityPhysicalTable, FieldDefinition
from apps.physical_tables.services import PhysicalTableGenerator, build_table_name
from apps.physical_tables.type_map import get_column_type

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace_id():
    return uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture()
def entity(workspace_id, db):
    """A minimal EntityDefinition with no physical table yet."""
    return EntityDefinition.objects.create(
        workspace_id=workspace_id,
        name="Lead",
        plural_name="Leads",
        slug="lead",
        table_name="",
        has_physical_table=False,
        current_schema_version=1,
    )


@pytest.fixture()
def entity_with_table(entity, db):
    """An entity that already has its physical table created."""
    PhysicalTableGenerator.create_table(entity)
    entity.refresh_from_db()
    return entity


@pytest.fixture()
def text_field(entity, db):
    """A promoted text field on the entity (before table creation)."""
    return FieldDefinition.objects.create(
        entity=entity,
        workspace_id=entity.workspace_id,
        name="Full Name",
        slug="full_name",
        field_type="text",
        is_promoted=True,
        is_filterable=True,
        is_sortable=True,
        is_required=True,
        order=0,
    )


@pytest.fixture()
def email_field(entity, db):
    """A promoted email field (not required)."""
    return FieldDefinition.objects.create(
        entity=entity,
        workspace_id=entity.workspace_id,
        name="Email",
        slug="email",
        field_type="email",
        is_promoted=True,
        is_filterable=True,
        is_sortable=False,
        order=1,
    )


# ---------------------------------------------------------------------------
# build_table_name
# ---------------------------------------------------------------------------

class TestBuildTableName:
    def test_format(self, workspace_id):
        name = build_table_name(workspace_id, "lead")
        assert name.startswith("nexus_t_")
        # First 8 hex chars of the UUID
        assert workspace_id.hex[:8] in name
        assert name.endswith("_lead")

    def test_hyphens_in_slug_replaced(self, workspace_id):
        name = build_table_name(workspace_id, "my-entity")
        assert "-" not in name
        assert "my_entity" in name

    def test_long_slug_truncated(self, workspace_id):
        long_slug = "a" * 100
        name = build_table_name(workspace_id, long_slug)
        assert len(name) <= 62

    def test_different_workspaces_different_names(self, workspace_id):
        ws2 = uuid.uuid4()
        n1 = build_table_name(workspace_id, "lead")
        n2 = build_table_name(ws2, "lead")
        assert n1 != n2


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.create_table
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateTable:
    def test_creates_physical_table_in_db(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        assert PhysicalTableGenerator.table_exists(entity.table_name)

    def test_updates_entity_flags(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        assert entity.has_physical_table is True
        assert entity.table_name != ""

    def test_creates_tracker_row(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        tracker = EntityPhysicalTable.objects.get(entity=entity)
        assert tracker.status == "ready"
        assert tracker.table_name == entity.table_name

    def test_tracker_lists_promoted_columns(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        tracker = EntityPhysicalTable.objects.get(entity=entity)
        slugs = [c["slug"] for c in tracker.promoted_columns]
        assert "full_name" in slugs

    def test_standard_columns_present(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        cols = PhysicalTableGenerator.get_table_columns(entity.table_name)
        col_names = {c["name"] for c in cols}
        for expected in ("id", "workspace_id", "created_at", "updated_at",
                         "custom_data", "deleted_at"):
            assert expected in col_names, f"Missing column: {expected}"

    def test_promoted_column_present(self, entity, text_field):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        cols = PhysicalTableGenerator.get_table_columns(entity.table_name)
        col_names = {c["name"] for c in cols}
        assert "full_name" in col_names

    def test_raises_if_already_has_table(self, entity_with_table):
        with pytest.raises(ValueError, match="already has a physical table"):
            PhysicalTableGenerator.create_table(entity_with_table)

    def test_no_promoted_fields_still_creates_table(self, entity):
        """Entity with zero promoted fields → only standard columns."""
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        assert PhysicalTableGenerator.table_exists(entity.table_name)
        cols = PhysicalTableGenerator.get_table_columns(entity.table_name)
        assert any(c["name"] == "workspace_id" for c in cols)

    def test_multiple_entities_get_different_tables(self, workspace_id, db):
        e1 = EntityDefinition.objects.create(
            workspace_id=workspace_id, name="Alpha", plural_name="Alphas",
            slug="alpha", table_name="", has_physical_table=False, current_schema_version=1,
        )
        e2 = EntityDefinition.objects.create(
            workspace_id=workspace_id, name="Beta", plural_name="Betas",
            slug="beta", table_name="", has_physical_table=False, current_schema_version=1,
        )
        PhysicalTableGenerator.create_table(e1)
        PhysicalTableGenerator.create_table(e2)
        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.table_name != e2.table_name
        assert PhysicalTableGenerator.table_exists(e1.table_name)
        assert PhysicalTableGenerator.table_exists(e2.table_name)


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.add_column
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAddColumn:
    def test_column_appears_in_db(self, entity_with_table, db):
        field = FieldDefinition.objects.create(
            entity=entity_with_table,
            workspace_id=entity_with_table.workspace_id,
            name="Score",
            slug="score",
            field_type="integer",
            is_promoted=False,
            order=10,
        )
        PhysicalTableGenerator.add_column(entity_with_table, field)
        cols = PhysicalTableGenerator.get_table_columns(entity_with_table.table_name)
        assert any(c["name"] == "score" for c in cols)

    def test_field_marked_promoted(self, entity_with_table, db):
        field = FieldDefinition.objects.create(
            entity=entity_with_table,
            workspace_id=entity_with_table.workspace_id,
            name="Score",
            slug="score",
            field_type="integer",
            is_promoted=False,
            order=10,
        )
        PhysicalTableGenerator.add_column(entity_with_table, field)
        field.refresh_from_db()
        assert field.is_promoted is True
        assert field.column_name == "score"

    def test_tracker_updated(self, entity_with_table, db):
        field = FieldDefinition.objects.create(
            entity=entity_with_table,
            workspace_id=entity_with_table.workspace_id,
            name="Score",
            slug="score",
            field_type="integer",
            is_promoted=False,
            order=10,
        )
        PhysicalTableGenerator.add_column(entity_with_table, field)
        tracker = entity_with_table.physical_table
        slugs = [c["slug"] for c in tracker.promoted_columns]
        assert "score" in slugs

    def test_raises_when_no_table(self, entity, db):
        field = FieldDefinition.objects.create(
            entity=entity,
            workspace_id=entity.workspace_id,
            name="X",
            slug="x",
            field_type="text",
            order=0,
        )
        with pytest.raises(ValueError, match="no physical table yet"):
            PhysicalTableGenerator.add_column(entity, field)

    def test_add_decimal_field(self, entity_with_table, db):
        field = FieldDefinition.objects.create(
            entity=entity_with_table,
            workspace_id=entity_with_table.workspace_id,
            name="Amount",
            slug="amount",
            field_type="decimal",
            config={"precision": 10, "scale": 2},
            is_promoted=False,
            order=20,
        )
        PhysicalTableGenerator.add_column(entity_with_table, field)
        cols = PhysicalTableGenerator.get_table_columns(entity_with_table.table_name)
        assert any(c["name"] == "amount" for c in cols)

    def test_add_boolean_field_with_default(self, entity_with_table, db):
        field = FieldDefinition.objects.create(
            entity=entity_with_table,
            workspace_id=entity_with_table.workspace_id,
            name="Is Active",
            slug="is_active",
            field_type="boolean",
            default_value=True,
            is_promoted=False,
            order=30,
        )
        PhysicalTableGenerator.add_column(entity_with_table, field)
        cols = PhysicalTableGenerator.get_table_columns(entity_with_table.table_name)
        assert any(c["name"] == "is_active" for c in cols)


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.drop_column  (metadata-level; DDL only on PG)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDropColumn:
    def test_field_marked_not_promoted(self, entity, text_field, db):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        text_field.refresh_from_db()
        PhysicalTableGenerator.drop_column(entity, text_field)
        text_field.refresh_from_db()
        assert text_field.is_promoted is False
        assert text_field.column_name == ""

    def test_tracker_updated(self, entity, text_field, db):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        text_field.refresh_from_db()
        PhysicalTableGenerator.drop_column(entity, text_field)
        tracker = entity.physical_table
        slugs = [c["slug"] for c in tracker.promoted_columns]
        assert "full_name" not in slugs

    def test_raises_when_no_table(self, entity, text_field, db):
        with pytest.raises(ValueError, match="no physical table yet"):
            PhysicalTableGenerator.drop_column(entity, text_field)


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.rename_column  (metadata-level; DDL only on PG)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRenameColumn:
    def test_column_name_updated_in_metadata(self, entity, text_field, db):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        text_field.refresh_from_db()
        PhysicalTableGenerator.rename_column(entity, text_field, "contact_name")
        text_field.refresh_from_db()
        assert text_field.column_name == "contact_name"

    def test_tracker_updated_on_rename(self, entity, text_field, db):
        PhysicalTableGenerator.create_table(entity)
        entity.refresh_from_db()
        text_field.refresh_from_db()
        PhysicalTableGenerator.rename_column(entity, text_field, "contact_name")
        tracker = entity.physical_table
        names = [c["column_name"] for c in tracker.promoted_columns]
        assert "contact_name" in names
        assert "full_name" not in names


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.drop_table
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDropTable:
    def test_table_removed_from_db(self, entity_with_table, db):
        table_name = entity_with_table.table_name
        PhysicalTableGenerator.drop_table(entity_with_table)
        assert not PhysicalTableGenerator.table_exists(table_name)

    def test_entity_flags_reset(self, entity_with_table, db):
        PhysicalTableGenerator.drop_table(entity_with_table)
        entity_with_table.refresh_from_db()
        assert entity_with_table.has_physical_table is False
        assert entity_with_table.table_name == ""

    def test_tracker_row_deleted(self, entity_with_table, db):
        PhysicalTableGenerator.drop_table(entity_with_table)
        assert not EntityPhysicalTable.objects.filter(
            entity=entity_with_table
        ).exists()

    def test_raises_when_no_table(self, entity, db):
        with pytest.raises(ValueError, match="no physical table yet"):
            PhysicalTableGenerator.drop_table(entity)


# ---------------------------------------------------------------------------
# PhysicalTableGenerator.table_exists / get_table_columns
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIntrospection:
    def test_table_exists_true(self, entity_with_table, db):
        assert PhysicalTableGenerator.table_exists(entity_with_table.table_name)

    def test_table_exists_false(self, db):
        assert not PhysicalTableGenerator.table_exists("nexus_t_nonexistent_table")

    def test_get_columns_returns_list(self, entity_with_table, db):
        cols = PhysicalTableGenerator.get_table_columns(entity_with_table.table_name)
        assert isinstance(cols, list)
        assert len(cols) > 0

    def test_get_columns_empty_for_missing_table(self, db):
        cols = PhysicalTableGenerator.get_table_columns("nexus_t_does_not_exist")
        assert cols == []


# ---------------------------------------------------------------------------
# type_map
# ---------------------------------------------------------------------------

class TestTypeMap:
    def test_known_types_sqlite(self):
        assert get_column_type("text", vendor="sqlite") == "TEXT"
        assert get_column_type("integer", vendor="sqlite") == "INTEGER"
        assert get_column_type("boolean", vendor="sqlite") == "INTEGER"

    def test_known_types_pg(self):
        assert get_column_type("email", vendor="postgresql") == "VARCHAR(254)"
        assert get_column_type("boolean", vendor="postgresql") == "BOOLEAN"
        assert get_column_type("datetime", vendor="postgresql") == "TIMESTAMPTZ"

    def test_unknown_type_falls_back_to_text(self):
        assert get_column_type("__unknown__", vendor="postgresql") == "TEXT"
        assert get_column_type("__unknown__", vendor="sqlite") == "TEXT"

    def test_decimal_precision_override(self):
        result = get_column_type("decimal", config={"precision": 12, "scale": 4},
                                 vendor="postgresql")
        assert "12" in result
        assert "4" in result

    def test_is_jsonb_type(self):
        from apps.physical_tables.type_map import is_jsonb_type
        assert is_jsonb_type("multi_select")
        assert is_jsonb_type("location")
        assert not is_jsonb_type("text")
        assert not is_jsonb_type("integer")
