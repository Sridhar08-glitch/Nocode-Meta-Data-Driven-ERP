"""
API-level tests for Schema Registry views.

Uses DRF APIClient with a fake authenticated user that carries workspace_id.
All tests run against the real SQLite test DB — no mocking the service layer.
"""
from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from apps.metadata.models import FieldDefinition
from apps.schema_registry.services import SchemaRegistryService

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKSPACE_ID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")


class FakeUser:
    """Minimal user object that view helpers can inspect."""

    def __init__(self, workspace_id=WORKSPACE_ID, uid=None):
        self.workspace_id = workspace_id
        self.id = uid or uuid.uuid4()
        self.pk = self.id
        self.is_authenticated = True


def authed_client(workspace_id=WORKSPACE_ID):
    """Return an APIClient with a fake authenticated user."""
    client = APIClient()
    client.force_authenticate(user=FakeUser(workspace_id=workspace_id))
    return client


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_BASE = "/api/v1/schema"


def url_entity_list():
    return f"{_BASE}/entities/"


def url_entity_detail(slug):
    return f"{_BASE}/entities/{slug}/"


def url_field_list(entity_slug):
    return f"{_BASE}/entities/{entity_slug}/fields/"


def url_field_detail(entity_slug, field_slug):
    return f"{_BASE}/entities/{entity_slug}/fields/{field_slug}/"


def url_version_list(entity_slug):
    return f"{_BASE}/entities/{entity_slug}/versions/"


def url_diff(entity_slug):
    return f"{_BASE}/entities/{entity_slug}/diff/"


def url_rollback(entity_slug):
    return f"{_BASE}/entities/{entity_slug}/rollback/"


# ---------------------------------------------------------------------------
# EntityListView  POST /api/schema/entities/
# ---------------------------------------------------------------------------

class TestEntityListView:
    def test_create_entity_returns_201(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={
                "slug": "invoice",
                "name": "Invoice",
                "plural_name": "Invoices",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["slug"] == "invoice"

    def test_create_entity_with_fields(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={
                "slug": "product",
                "name": "Product",
                "plural_name": "Products",
                "fields": [
                    {
                        "slug": "sku",
                        "name": "SKU",
                        "field_type": "text",
                        "is_promoted": True,
                    }
                ],
            },
            format="json",
        )
        assert resp.status_code == 201
        field_slugs = [f["slug"] for f in resp.data["fields"]]
        assert "sku" in field_slugs

    def test_create_entity_duplicate_slug_returns_400(self):
        client = authed_client()
        client.post(
            url_entity_list(),
            data={"slug": "lead", "name": "Lead", "plural_name": "Leads"},
            format="json",
        )
        resp = client.post(
            url_entity_list(),
            data={"slug": "lead", "name": "Lead2", "plural_name": "Leads2"},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_entity_invalid_slug_returns_400(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={"slug": "123bad", "name": "Bad", "plural_name": "Bads"},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_entity_missing_required_fields_returns_400(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={"slug": "only_slug"},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_entity_duplicate_field_slugs_returns_400(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={
                "slug": "widget",
                "name": "Widget",
                "plural_name": "Widgets",
                "fields": [
                    {"slug": "col", "name": "Col A", "field_type": "text"},
                    {"slug": "col", "name": "Col B", "field_type": "text"},
                ],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_response_shape(self):
        client = authed_client()
        resp = client.post(
            url_entity_list(),
            data={"slug": "task", "name": "Task", "plural_name": "Tasks"},
            format="json",
        )
        assert resp.status_code == 201
        for key in ("id", "slug", "name", "plural_name", "table_name", "has_physical_table", "fields"):
            assert key in resp.data

    def test_unauthenticated_returns_403_or_401(self):
        client = APIClient()  # no auth
        resp = client.post(
            url_entity_list(),
            data={"slug": "x", "name": "X", "plural_name": "Xs"},
            format="json",
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# EntityDetailView  GET /api/schema/entities/{slug}/
# ---------------------------------------------------------------------------

class TestEntityDetailView:
    def _create(self, slug="contact"):
        SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug=slug,
            name=slug.capitalize(),
            plural_name=slug.capitalize() + "s",
        )

    def test_get_existing_entity_returns_200(self):
        self._create("account")
        client = authed_client()
        resp = client.get(url_entity_detail("account"))
        assert resp.status_code == 200
        assert resp.data["slug"] == "account"

    def test_get_nonexistent_returns_404(self):
        client = authed_client()
        resp = client.get(url_entity_detail("nonexistent"))
        assert resp.status_code == 404

    def test_schema_includes_fields_key(self):
        self._create("deal")
        client = authed_client()
        resp = client.get(url_entity_detail("deal"))
        assert "fields" in resp.data

    def test_workspace_isolation(self):
        """Entity created in workspace A is not visible to workspace B."""
        SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug="secret",
            name="Secret",
            plural_name="Secrets",
        )
        other_ws = uuid.UUID("11112222-3333-4444-5555-666677778888")
        client_b = authed_client(workspace_id=other_ws)
        resp = client_b.get(url_entity_detail("secret"))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# FieldListView  POST /api/schema/entities/{slug}/fields/
# ---------------------------------------------------------------------------

class TestFieldListView:
    def _entity(self, slug="lead"):
        return SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug=slug,
            name=slug.capitalize(),
            plural_name=slug.capitalize() + "s",
        )

    def test_add_field_returns_201(self):
        self._entity("invoice")
        client = authed_client()
        resp = client.post(
            url_field_list("invoice"),
            data={"slug": "due_date", "name": "Due Date", "field_type": "date"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["slug"] == "due_date"

    def test_add_field_to_nonexistent_entity_returns_404(self):
        client = authed_client()
        resp = client.post(
            url_field_list("ghost"),
            data={"slug": "col", "name": "Col", "field_type": "text"},
            format="json",
        )
        assert resp.status_code == 404

    def test_add_duplicate_field_returns_400(self):
        self._entity("project")
        client = authed_client()
        client.post(
            url_field_list("project"),
            data={"slug": "status", "name": "Status", "field_type": "select"},
            format="json",
        )
        resp = client.post(
            url_field_list("project"),
            data={"slug": "status", "name": "Status2", "field_type": "select"},
            format="json",
        )
        assert resp.status_code == 400

    def test_add_field_invalid_type_returns_400(self):
        self._entity("asset")
        client = authed_client()
        resp = client.post(
            url_field_list("asset"),
            data={"slug": "col", "name": "Col", "field_type": "not_real"},
            format="json",
        )
        assert resp.status_code == 400

    def test_add_promoted_field_success(self):
        self._entity("employee")
        client = authed_client()
        resp = client.post(
            url_field_list("employee"),
            data={
                "slug": "department",
                "name": "Department",
                "field_type": "text",
                "is_promoted": True,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["is_promoted"] is True


# ---------------------------------------------------------------------------
# FieldDetailView  PATCH + DELETE
# ---------------------------------------------------------------------------

class TestFieldDetailView:
    def _setup(self):
        entity = SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug="ticket",
            name="Ticket",
            plural_name="Tickets",
            fields=[{"slug": "priority", "name": "Priority", "field_type": "select"}],
        )
        return entity

    def test_patch_field_returns_200(self):
        self._setup()
        client = authed_client()
        resp = client.patch(
            url_field_detail("ticket", "priority"),
            data={"name": "Urgency Level"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["name"] == "Urgency Level"

    def test_patch_nonexistent_field_returns_404(self):
        self._setup()
        client = authed_client()
        resp = client.patch(
            url_field_detail("ticket", "ghost_field"),
            data={"name": "X"},
            format="json",
        )
        assert resp.status_code == 404

    def test_patch_nonexistent_entity_returns_404(self):
        client = authed_client()
        resp = client.patch(
            url_field_detail("nonexistent_entity", "col"),
            data={"name": "X"},
            format="json",
        )
        assert resp.status_code == 404

    def test_patch_empty_body_returns_400(self):
        self._setup()
        client = authed_client()
        resp = client.patch(
            url_field_detail("ticket", "priority"),
            data={},
            format="json",
        )
        assert resp.status_code == 400

    def test_delete_field_returns_204(self):
        self._setup()
        client = authed_client()
        resp = client.delete(url_field_detail("ticket", "priority"))
        assert resp.status_code == 204

    def test_delete_nonexistent_field_returns_404(self):
        self._setup()
        client = authed_client()
        resp = client.delete(url_field_detail("ticket", "does_not_exist"))
        assert resp.status_code == 404

    def test_delete_system_field_returns_403(self):
        entity = self._setup()
        # Manually create a system field
        FieldDefinition.objects.create(
            entity=entity,
            workspace_id=WORKSPACE_ID,
            slug="sys_field",
            name="System Field",
            field_type="text",
            is_system=True,
        )
        client = authed_client()
        resp = client.delete(url_field_detail("ticket", "sys_field"))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# SchemaVersionListView  GET /api/schema/entities/{slug}/versions/
# ---------------------------------------------------------------------------

class TestSchemaVersionListView:
    def _entity(self):
        return SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug="sprint",
            name="Sprint",
            plural_name="Sprints",
        )

    def test_list_versions_returns_200(self):
        self._entity()
        client = authed_client()
        resp = client.get(url_version_list("sprint"))
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) >= 1

    def test_list_versions_nonexistent_entity_returns_404(self):
        client = authed_client()
        resp = client.get(url_version_list("ghost"))
        assert resp.status_code == 404

    def test_version_items_have_expected_keys(self):
        self._entity()
        client = authed_client()
        resp = client.get(url_version_list("sprint"))
        assert resp.status_code == 200
        item = resp.data[0]
        for key in ("id", "version", "snapshot", "is_current"):
            assert key in item

    def test_newest_version_first(self):
        self._entity()
        SchemaRegistryService.add_field(
            workspace_id=WORKSPACE_ID,
            entity_slug="sprint",
            slug="goal",
            name="Goal",
            field_type="text",
        )
        client = authed_client()
        resp = client.get(url_version_list("sprint"))
        assert resp.status_code == 200
        versions = [item["version"] for item in resp.data]
        assert versions == sorted(versions, reverse=True)


# ---------------------------------------------------------------------------
# SchemaDiffView  GET /api/schema/entities/{slug}/diff/
# ---------------------------------------------------------------------------

class TestSchemaDiffView:
    def _setup(self):
        entity = SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug="deal",
            name="Deal",
            plural_name="Deals",
        )
        SchemaRegistryService.add_field(
            workspace_id=WORKSPACE_ID,
            entity_slug="deal",
            slug="amount",
            name="Amount",
            field_type="decimal",
        )
        return entity

    def test_diff_returns_200(self):
        self._setup()
        client = authed_client()
        resp = client.get(url_diff("deal"), {"version_a": 1, "version_b": 2})
        assert resp.status_code == 200

    def test_diff_response_shape(self):
        self._setup()
        client = authed_client()
        resp = client.get(url_diff("deal"), {"version_a": 1, "version_b": 2})
        assert resp.status_code == 200
        for key in ("version_a", "version_b", "added", "removed", "changed"):
            assert key in resp.data

    def test_diff_missing_params_returns_400(self):
        self._setup()
        client = authed_client()
        resp = client.get(url_diff("deal"), {"version_a": 1})
        assert resp.status_code == 400

    def test_diff_same_version_returns_400(self):
        self._setup()
        client = authed_client()
        resp = client.get(url_diff("deal"), {"version_a": 1, "version_b": 1})
        assert resp.status_code == 400

    def test_diff_nonexistent_version_returns_404(self):
        self._setup()
        client = authed_client()
        resp = client.get(url_diff("deal"), {"version_a": 1, "version_b": 99})
        assert resp.status_code == 404

    def test_diff_nonexistent_entity_returns_404(self):
        client = authed_client()
        resp = client.get(url_diff("ghost"), {"version_a": 1, "version_b": 2})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SchemaRollbackView  POST /api/schema/entities/{slug}/rollback/
# ---------------------------------------------------------------------------

class TestSchemaRollbackView:
    def _setup(self):
        entity = SchemaRegistryService.create_entity(
            workspace_id=WORKSPACE_ID,
            slug="order",
            name="Order",
            plural_name="Orders",
        )
        SchemaRegistryService.add_field(
            workspace_id=WORKSPACE_ID,
            entity_slug="order",
            slug="discount",
            name="Discount",
            field_type="decimal",
        )
        return entity

    def test_rollback_returns_200(self):
        self._setup()
        client = authed_client()
        resp = client.post(
            url_rollback("order"),
            data={"target_version": 1},
            format="json",
        )
        assert resp.status_code == 200

    def test_rollback_removes_field(self):
        entity = self._setup()
        client = authed_client()
        client.post(
            url_rollback("order"),
            data={"target_version": 1},
            format="json",
        )
        entity.refresh_from_db()
        assert not entity.fields.filter(slug="discount").exists()

    def test_rollback_to_nonexistent_version_returns_404(self):
        self._setup()
        client = authed_client()
        resp = client.post(
            url_rollback("order"),
            data={"target_version": 999},
            format="json",
        )
        assert resp.status_code == 404

    def test_rollback_to_nonexistent_entity_returns_404(self):
        client = authed_client()
        resp = client.post(
            url_rollback("ghost"),
            data={"target_version": 1},
            format="json",
        )
        assert resp.status_code == 404

    def test_rollback_missing_body_returns_400(self):
        self._setup()
        client = authed_client()
        resp = client.post(url_rollback("order"), data={}, format="json")
        assert resp.status_code == 400

    def test_rollback_response_shape(self):
        self._setup()
        client = authed_client()
        resp = client.post(
            url_rollback("order"),
            data={"target_version": 1},
            format="json",
        )
        assert resp.status_code == 200
        for key in ("id", "slug", "name", "has_physical_table", "fields"):
            assert key in resp.data
