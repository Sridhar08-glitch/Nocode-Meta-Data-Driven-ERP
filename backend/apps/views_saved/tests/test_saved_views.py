"""Saved Views API (master spec §49)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _client(ws, email):
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role="member", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.mark.django_db
class TestSavedViews:
    def test_crud(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        c = _client(ws, "sv@acme.com")
        SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")

        created = c.post("/api/v1/saved-views/",
                         {"entity_slug": "lead", "name": "My Open", "is_pinned": True,
                          "sort_overrides": [{"field": "name", "direction": "asc"}]}, format="json")
        assert created.status_code == 201
        vid = created.data["id"]

        lst = c.get("/api/v1/saved-views/", {"entity_slug": "lead"})
        assert lst.data["count"] == 1 and lst.data["results"][0]["is_pinned"] is True

        upd = c.patch(f"/api/v1/saved-views/{vid}/", {"name": "Renamed"}, format="json")
        assert upd.status_code == 200 and upd.data["name"] == "Renamed"

        assert c.delete(f"/api/v1/saved-views/{vid}/").status_code == 204
        assert c.get("/api/v1/saved-views/").data["count"] == 0

    def test_isolation_between_members(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        c1 = _client(ws, "m1@acme.com")
        c2 = _client(ws, "m2@acme.com")
        c1.post("/api/v1/saved-views/", {"entity_slug": "lead", "name": "Mine"}, format="json")
        assert c2.get("/api/v1/saved-views/").data["count"] == 0   # not visible to other member
