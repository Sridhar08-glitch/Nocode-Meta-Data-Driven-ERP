"""Impact analysis (Phase P1.4) — entity/field dependency scan endpoints."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import FormDefinition
from apps.rules.models import BusinessRule
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/metadata"


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def client(workspace):
    user = User.objects.create_user(email="b@acme.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="admin", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


@pytest.fixture
def entity(workspace):
    SchemaRegistryService.create_entity(workspace_id=workspace.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead", slug="status",
                                    name="Status", field_type="text", is_promoted=True)
    return SchemaRegistryService.get_entity(workspace_id=workspace.id, slug="lead")


@pytest.mark.django_db
class TestImpact:
    def test_field_impact_reports_form_and_rule(self, client, workspace, entity):
        FormDefinition.objects.create(
            workspace_id=workspace.id, entity_id=entity.id, name="Lead form",
            layout=[{"section": "main", "fields": ["status"]}], settings={})
        BusinessRule.objects.create(
            workspace_id=workspace.id, entity_id=entity.id, name="Status watcher", slug="status_watcher",
            trigger_on="before_update", watch_field_slug="status", actions=[], condition_nql="")

        r = client.get(f"{BASE}/entities/lead/fields/status/impact/")
        assert r.status_code == 200
        types = {d["type"] for d in r.data["dependents"]}
        assert "form" in types and "rule" in types
        assert r.data["count"] >= 2

    def test_field_impact_empty_for_unreferenced_field(self, client, workspace, entity):
        SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead", slug="notes",
                                        name="Notes", field_type="text", is_promoted=True)
        r = client.get(f"{BASE}/entities/lead/fields/notes/impact/")
        assert r.status_code == 200
        assert r.data["count"] == 0

    def test_entity_impact_reports_form(self, client, workspace, entity):
        FormDefinition.objects.create(
            workspace_id=workspace.id, entity_id=entity.id, name="Lead form", layout=[], settings={})
        r = client.get(f"{BASE}/entities/lead/impact/")
        assert r.status_code == 200
        assert any(d["type"] == "form" for d in r.data["dependents"])

    def test_field_impact_404_for_missing_field(self, client, entity):
        assert client.get(f"{BASE}/entities/lead/fields/nope/impact/").status_code == 404
