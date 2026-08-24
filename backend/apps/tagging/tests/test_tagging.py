"""Universal tagging API (master spec §48)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _client(ws, email):
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.mark.django_db
class TestTagging:
    def test_create_attach_list_detach(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        c = _client(ws, "tag@acme.com")
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                        name="Name", field_type="text", is_promoted=True)
        ent.refresh_from_db()
        rid = c.post("/api/v1/data/lead/", {"name": "A"}, format="json").data["id"]

        tag = c.post("/api/v1/tags/", {"name": "VIP", "slug": "vip"}, format="json")
        assert tag.status_code == 201
        tag_id = tag.data["id"]

        att = c.post("/api/v1/tags/records/",
                     {"entity_slug": "lead", "tag_id": tag_id, "record_id": rid}, format="json")
        assert att.status_code == 201

        lst = c.get("/api/v1/tags/records/", {"record_id": rid})
        assert any(t["slug"] == "vip" for t in lst.data["results"])

        det = c.delete("/api/v1/tags/records/",
                       {"tag_id": tag_id, "record_id": rid}, format="json")
        assert det.data["removed"] >= 1
        assert c.get("/api/v1/tags/records/", {"record_id": rid}).data["count"] == 0
