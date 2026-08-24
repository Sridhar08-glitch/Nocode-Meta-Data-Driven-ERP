"""
Integration tests for SchemaRegistryService.

Runs against the real SQLite test database — validates the full lifecycle:
create → add_field → update_field → remove_field → versions → diff → rollback.

No mocks for DB; PhysicalTableGenerator is called for real (SQLite variant).
"""
from __future__ import annotations

import uuid

import pytest

from apps.metadata.models import EntityDefinition, FieldDefinition, SchemaVersion
from apps.physical_tables.services import PhysicalTableGenerator
from apps.schema_registry.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    FieldAlreadyExistsError,
    FieldNotFoundError,
    InvalidFieldTypeError,
    InvalidSlugError,
    SchemaVersionNotFoundError,
    SystemFieldError,
)
from apps.schema_registry.services import SchemaRegistryService

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace_id():
    return uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture()
def other_workspace_id():
    return uuid.UUID("11112222-3333-4444-5555-666677778888")


@pytest.fixture()
def basic_entity(workspace_id):
    """Create a minimal entity via the service."""
    return SchemaRegistryService.create_entity(
        workspace_id=workspace_id,
        slug="lead",
        name="Lead",
        plural_name="Leads",
    )


@pytest.fixture()
def entity_with_field(workspace_id):
    """Entity with one promoted text field."""
    entity = SchemaRegistryService.create_entity(
        workspace_id=workspace_id,
        slug="contact",
        name="Contact",
        plural_name="Contacts",
        fields=[
            {
                "slug": "full_name",
                "name": "Full Name",
                "field_type": "text",
                "is_promoted": True,
                "order": 0,
            }
        ],
    )
    return entity


# ---------------------------------------------------------------------------
# create_entity
# ---------------------------------------------------------------------------

class TestCreateEntity:
    def test_returns_entity_definition(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="invoice",
            name="Invoice",
            plural_name="Invoices",
        )
        assert isinstance(entity, EntityDefinition)
        assert entity.slug == "invoice"

    def test_entity_has_physical_table(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="product",
            name="Product",
            plural_name="Products",
        )
        assert entity.has_physical_table is True
        assert entity.table_name != ""
        assert PhysicalTableGenerator.table_exists(entity.table_name)

    def test_schema_version_one_created(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="task",
            name="Task",
            plural_name="Tasks",
        )
        sv = SchemaVersion.objects.get(entity=entity, is_current=True)
        assert sv.version == 1
        assert sv.is_current is True

    def test_fields_created_from_spec(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="deal",
            name="Deal",
            plural_name="Deals",
            fields=[
                {"slug": "title", "name": "Title", "field_type": "text", "order": 0},
                {"slug": "amount", "name": "Amount", "field_type": "decimal", "order": 1},
            ],
        )
        slugs = list(entity.fields.values_list("slug", flat=True))
        assert "title" in slugs
        assert "amount" in slugs

    def test_promoted_fields_appear_in_physical_table(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="employee",
            name="Employee",
            plural_name="Employees",
            fields=[
                {
                    "slug": "email",
                    "name": "Email",
                    "field_type": "email",
                    "is_promoted": True,
                    "order": 0,
                }
            ],
        )
        cols = PhysicalTableGenerator.get_table_columns(entity.table_name)
        col_names = {c["name"] for c in cols}
        assert "email" in col_names

    def test_duplicate_slug_raises(self, basic_entity, workspace_id):
        with pytest.raises(EntityAlreadyExistsError):
            SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug="lead",
                name="Lead2",
                plural_name="Leads2",
            )

    def test_invalid_entity_slug_raises(self, workspace_id):
        with pytest.raises(InvalidSlugError):
            SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug="123bad",
                name="Bad",
                plural_name="Bads",
            )

    def test_invalid_field_slug_in_spec_raises(self, workspace_id):
        with pytest.raises(InvalidSlugError):
            SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug="good",
                name="Good",
                plural_name="Goods",
                fields=[{"slug": "BAD SLUG!", "name": "X", "field_type": "text"}],
            )

    def test_invalid_field_type_raises(self, workspace_id):
        with pytest.raises(InvalidFieldTypeError):
            SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug="thing",
                name="Thing",
                plural_name="Things",
                fields=[{"slug": "col", "name": "Col", "field_type": "nonexistent_type"}],
            )

    def test_duplicate_field_slugs_in_spec_raises(self, workspace_id):
        with pytest.raises(FieldAlreadyExistsError):
            SchemaRegistryService.create_entity(
                workspace_id=workspace_id,
                slug="widget",
                name="Widget",
                plural_name="Widgets",
                fields=[
                    {"slug": "name", "name": "Name", "field_type": "text"},
                    {"slug": "name", "name": "Name2", "field_type": "text"},
                ],
            )

    def test_same_slug_different_workspace_is_allowed(self, workspace_id, other_workspace_id):
        e1 = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="project",
            name="Project",
            plural_name="Projects",
        )
        e2 = SchemaRegistryService.create_entity(
            workspace_id=other_workspace_id,
            slug="project",
            name="Project",
            plural_name="Projects",
        )
        assert e1.pk != e2.pk
        assert e1.table_name != e2.table_name


# ---------------------------------------------------------------------------
# get_entity / get_entity_schema
# ---------------------------------------------------------------------------

class TestGetEntity:
    def test_get_entity_returns_object(self, basic_entity, workspace_id):
        entity = SchemaRegistryService.get_entity(
            workspace_id=workspace_id, slug="lead"
        )
        assert entity.pk == basic_entity.pk

    def test_get_entity_not_found_raises(self, workspace_id):
        with pytest.raises(EntityNotFoundError):
            SchemaRegistryService.get_entity(
                workspace_id=workspace_id, slug="nonexistent"
            )

    def test_get_entity_schema_returns_dict(self, basic_entity, workspace_id):
        schema = SchemaRegistryService.get_entity_schema(
            workspace_id=workspace_id, slug="lead"
        )
        assert isinstance(schema, dict)
        assert schema["slug"] == "lead"
        assert "fields" in schema


# ---------------------------------------------------------------------------
# add_field
# ---------------------------------------------------------------------------

class TestAddField:
    def test_add_field_creates_field_definition(self, basic_entity, workspace_id):
        fd = SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="lead",
            slug="status",
            name="Status",
            field_type="select",
        )
        assert isinstance(fd, FieldDefinition)
        assert fd.slug == "status"

    def test_add_promoted_field_updates_table(self, basic_entity, workspace_id):
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="lead",
            slug="score",
            name="Score",
            field_type="integer",
            is_promoted=True,
        )
        basic_entity.refresh_from_db()
        cols = PhysicalTableGenerator.get_table_columns(basic_entity.table_name)
        assert any(c["name"] == "score" for c in cols)

    def test_add_field_bumps_schema_version(self, basic_entity, workspace_id):
        before_version = basic_entity.current_schema_version
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="lead",
            slug="phone",
            name="Phone",
            field_type="phone",
        )
        basic_entity.refresh_from_db()
        assert basic_entity.current_schema_version == before_version + 1

    def test_add_field_duplicate_slug_raises(self, basic_entity, workspace_id):
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="lead",
            slug="email",
            name="Email",
            field_type="email",
        )
        with pytest.raises(FieldAlreadyExistsError):
            SchemaRegistryService.add_field(
                workspace_id=workspace_id,
                entity_slug="lead",
                slug="email",
                name="Email2",
                field_type="email",
            )

    def test_add_field_invalid_type_raises(self, basic_entity, workspace_id):
        with pytest.raises(InvalidFieldTypeError):
            SchemaRegistryService.add_field(
                workspace_id=workspace_id,
                entity_slug="lead",
                slug="x",
                name="X",
                field_type="fake_type",
            )

    def test_add_field_to_missing_entity_raises(self, workspace_id):
        with pytest.raises(EntityNotFoundError):
            SchemaRegistryService.add_field(
                workspace_id=workspace_id,
                entity_slug="nonexistent",
                slug="x",
                name="X",
                field_type="text",
            )


# ---------------------------------------------------------------------------
# remove_field
# ---------------------------------------------------------------------------

class TestRemoveField:
    def test_remove_field_deletes_field_definition(self, entity_with_field, workspace_id):
        before_count = entity_with_field.fields.count()
        SchemaRegistryService.remove_field(
            workspace_id=workspace_id,
            entity_slug="contact",
            field_slug="full_name",
        )
        assert entity_with_field.fields.count() == before_count - 1

    def test_remove_field_bumps_schema_version(self, entity_with_field, workspace_id):
        before = entity_with_field.current_schema_version
        SchemaRegistryService.remove_field(
            workspace_id=workspace_id,
            entity_slug="contact",
            field_slug="full_name",
        )
        entity_with_field.refresh_from_db()
        assert entity_with_field.current_schema_version == before + 1

    def test_remove_nonexistent_field_raises(self, basic_entity, workspace_id):
        with pytest.raises(FieldNotFoundError):
            SchemaRegistryService.remove_field(
                workspace_id=workspace_id,
                entity_slug="lead",
                field_slug="does_not_exist",
            )

    def test_remove_system_field_raises(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="thing2",
            name="Thing",
            plural_name="Things",
        )
        # Manually create a system field
        FieldDefinition.objects.create(
            entity=entity,
            workspace_id=workspace_id,
            slug="sys_col",
            name="System Col",
            field_type="text",
            is_system=True,
        )
        with pytest.raises(SystemFieldError):
            SchemaRegistryService.remove_field(
                workspace_id=workspace_id,
                entity_slug="thing2",
                field_slug="sys_col",
            )


# ---------------------------------------------------------------------------
# update_field
# ---------------------------------------------------------------------------

class TestUpdateField:
    def test_update_field_name(self, entity_with_field, workspace_id):
        fd = SchemaRegistryService.update_field(
            workspace_id=workspace_id,
            entity_slug="contact",
            field_slug="full_name",
            updates={"name": "Contact Name"},
        )
        assert fd.name == "Contact Name"

    def test_update_field_promotes_column(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="order",
            name="Order",
            plural_name="Orders",
            fields=[{"slug": "note", "name": "Note", "field_type": "text", "is_promoted": False}],
        )
        SchemaRegistryService.update_field(
            workspace_id=workspace_id,
            entity_slug="order",
            field_slug="note",
            updates={"is_promoted": True},
        )
        entity.refresh_from_db()
        cols = PhysicalTableGenerator.get_table_columns(entity.table_name)
        assert any(c["name"] == "note" for c in cols)

    def test_update_field_demotes_column(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="account",
            name="Account",
            plural_name="Accounts",
            fields=[{
                "slug": "website",
                "name": "Website",
                "field_type": "url",
                "is_promoted": True,
            }],
        )
        SchemaRegistryService.update_field(
            workspace_id=workspace_id,
            entity_slug="account",
            field_slug="website",
            updates={"is_promoted": False},
        )
        fd = FieldDefinition.objects.get(entity=entity, slug="website")
        assert fd.is_promoted is False

    def test_update_field_bumps_schema_version(self, entity_with_field, workspace_id):
        before = entity_with_field.current_schema_version
        SchemaRegistryService.update_field(
            workspace_id=workspace_id,
            entity_slug="contact",
            field_slug="full_name",
            updates={"is_required": True},
        )
        entity_with_field.refresh_from_db()
        assert entity_with_field.current_schema_version == before + 1

    def test_update_nonexistent_field_raises(self, basic_entity, workspace_id):
        with pytest.raises(FieldNotFoundError):
            SchemaRegistryService.update_field(
                workspace_id=workspace_id,
                entity_slug="lead",
                field_slug="ghost",
                updates={"name": "Ghost"},
            )


# ---------------------------------------------------------------------------
# list_versions
# ---------------------------------------------------------------------------

class TestListVersions:
    def test_list_versions_returns_list(self, basic_entity, workspace_id):
        versions = SchemaRegistryService.list_versions(
            workspace_id=workspace_id,
            entity_slug="lead",
        )
        assert len(versions) >= 1

    def test_add_field_adds_version(self, basic_entity, workspace_id):
        before_count = SchemaVersion.objects.filter(entity=basic_entity).count()
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="lead",
            slug="notes",
            name="Notes",
            field_type="textarea",
        )
        after_count = SchemaVersion.objects.filter(entity=basic_entity).count()
        assert after_count == before_count + 1

    def test_only_one_current_version_at_a_time(self, entity_with_field, workspace_id):
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="contact",
            slug="phone",
            name="Phone",
            field_type="phone",
        )
        current_count = SchemaVersion.objects.filter(
            entity=entity_with_field, is_current=True
        ).count()
        assert current_count == 1


# ---------------------------------------------------------------------------
# diff_versions
# ---------------------------------------------------------------------------

class TestDiffVersions:
    def test_diff_returns_dict_with_keys(self, workspace_id):
        SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="project",
            name="Project",
            plural_name="Projects",
        )
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="project",
            slug="due_date",
            name="Due Date",
            field_type="date",
        )
        diff = SchemaRegistryService.diff_versions(
            workspace_id=workspace_id,
            entity_slug="project",
            version_a=1,
            version_b=2,
        )
        assert "added" in diff
        assert "removed" in diff
        assert "changed" in diff
        assert diff["version_a"] == 1
        assert diff["version_b"] == 2

    def test_diff_added_field_detected(self, workspace_id):
        SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="asset",
            name="Asset",
            plural_name="Assets",
        )
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="asset",
            slug="serial",
            name="Serial",
            field_type="text",
        )
        diff = SchemaRegistryService.diff_versions(
            workspace_id=workspace_id,
            entity_slug="asset",
            version_a=1,
            version_b=2,
        )
        added_slugs = [f["slug"] for f in diff["added"]]
        assert "serial" in added_slugs

    def test_diff_missing_version_raises(self, basic_entity, workspace_id):
        with pytest.raises(SchemaVersionNotFoundError):
            SchemaRegistryService.diff_versions(
                workspace_id=workspace_id,
                entity_slug="lead",
                version_a=1,
                version_b=99,
            )


# ---------------------------------------------------------------------------
# rollback_to_version
# ---------------------------------------------------------------------------

class TestRollbackToVersion:
    def test_rollback_restores_fields(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="ticket",
            name="Ticket",
            plural_name="Tickets",
        )
        # v1: no user fields
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="ticket",
            slug="priority",
            name="Priority",
            field_type="select",
        )
        # v2: priority exists — refresh required to see related-object changes
        entity.refresh_from_db()
        assert entity.fields.filter(slug="priority").exists() is True

        # Rollback to v1 — priority should be gone
        SchemaRegistryService.rollback_to_version(
            workspace_id=workspace_id,
            entity_slug="ticket",
            target_version=1,
        )
        entity.refresh_from_db()
        assert entity.fields.filter(slug="priority").exists() is False

    def test_rollback_bumps_schema_version(self, workspace_id):
        entity = SchemaRegistryService.create_entity(
            workspace_id=workspace_id,
            slug="sprint",
            name="Sprint",
            plural_name="Sprints",
        )
        SchemaRegistryService.add_field(
            workspace_id=workspace_id,
            entity_slug="sprint",
            slug="goal",
            name="Goal",
            field_type="text",
        )
        before = entity.current_schema_version
        SchemaRegistryService.rollback_to_version(
            workspace_id=workspace_id,
            entity_slug="sprint",
            target_version=1,
        )
        entity.refresh_from_db()
        assert entity.current_schema_version == before + 1

    def test_rollback_to_nonexistent_version_raises(self, basic_entity, workspace_id):
        with pytest.raises(SchemaVersionNotFoundError):
            SchemaRegistryService.rollback_to_version(
                workspace_id=workspace_id,
                entity_slug="lead",
                target_version=999,
            )
