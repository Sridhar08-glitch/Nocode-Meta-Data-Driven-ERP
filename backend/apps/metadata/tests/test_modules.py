"""Modules API (frontend F1.4 sidebar grouping) — /api/v1/metadata/modules/."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import Module
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/metadata/modules"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(ws, role="admin", email=None):
    user = User.objects.create_user(email=email or f"{role}@acme.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.mark.django_db
class TestModulesApi:
    def test_crud_and_order(self, ws):
        c = _client(ws, "admin")
        c.post(f"{BASE}/", {"name": "CRM", "slug": "crm", "order": 2}, format="json")
        c.post(f"{BASE}/", {"name": "HR", "slug": "hr", "order": 1}, format="json")
        listed = c.get(f"{BASE}/").data
        assert [m["slug"] for m in listed] == ["hr", "crm"]  # ordered by `order`

    def test_member_can_read_admin_writes(self, ws):
        _client(ws, "admin", email="a@acme.com").post(
            f"{BASE}/", {"name": "CRM", "slug": "crm"}, format="json")
        m = _client(ws, "member", email="m@acme.com")
        assert m.get(f"{BASE}/").status_code == 200
        assert m.post(f"{BASE}/", {"name": "X", "slug": "x"}, format="json").status_code == 403

    def test_cross_workspace_isolation(self, ws):
        _client(ws, "admin", email="a@acme.com").post(
            f"{BASE}/", {"name": "CRM", "slug": "crm"}, format="json")
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc = _client(other, "admin", email="o@other.com")
        assert oc.get(f"{BASE}/").data == []

    def test_entity_output_exposes_module(self, ws):
        from apps.schema_registry.services import SchemaRegistryService
        mod = Module.objects.create(workspace_id=ws.id, name="CRM", slug="crm")
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        ent.module_id = mod.id
        ent.save(update_fields=["module"])
        c = _client(ws, "admin")
        data = c.get("/api/v1/metadata/entities/").data
        lead = next(e for e in data if e["slug"] == "lead")
        assert str(lead["module"]) == str(mod.id)


@pytest.mark.django_db
class TestEntityPermissionAnnotation:
    def test_entities_annotated_with_can_read_can_create(self, ws):
        from apps.schema_registry.services import SchemaRegistryService
        SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        admin = _client(ws, "admin", email="a@acme.com")
        a_row = next(e for e in admin.get("/api/v1/metadata/entities/").data if e["slug"] == "lead")
        assert a_row["can_read"] is True and a_row["can_create"] is True
        # viewer role: read yes, create no
        viewer = _client(ws, "viewer", email="v@acme.com")
        v_row = next(e for e in viewer.get("/api/v1/metadata/entities/").data if e["slug"] == "lead")
        assert v_row["can_read"] is True and v_row["can_create"] is False
