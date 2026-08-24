"""
End-to-end tests for the Metadata CRUD API (/api/v1/metadata/).

These exercise the full stack: real JWT auth → TenantMiddleware (membership +
workspace resolution) → views → SchemaRegistryService → physical tables.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/metadata"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="builder@example.com", password=PW, is_verified=True)


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def client(user, workspace):
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="admin", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


def _create_entity(client, slug="lead", name="Lead", plural="Leads"):
    return client.post(f"{BASE}/entities/",
                       {"slug": slug, "name": name, "plural_name": plural}, format="json")


@pytest.mark.django_db
class TestEntityCrud:
    def test_create_entity_provisions_table(self, client, workspace):
        r = _create_entity(client)
        assert r.status_code == 201
        ent = EntityDefinition.objects.get(workspace_id=workspace.id, slug="lead")
        assert ent.has_physical_table is True
        assert ent.table_name

    def test_list_entities(self, client):
        _create_entity(client, slug="lead")
        _create_entity(client, slug="deal", name="Deal", plural="Deals")
        r = client.get(f"{BASE}/entities/")
        assert r.status_code == 200
        slugs = {e["slug"] for e in r.data}
        assert {"lead", "deal"} <= slugs

    def test_get_entity_schema(self, client):
        _create_entity(client)
        r = client.get(f"{BASE}/entities/lead/")
        assert r.status_code == 200
        assert r.data["slug"] == "lead"
        assert "fields" in r.data

    def test_patch_entity(self, client):
        _create_entity(client)
        r = client.patch(f"{BASE}/entities/lead/", {"name": "Prospect"}, format="json")
        assert r.status_code == 200
        assert r.data["name"] == "Prospect"

    def test_soft_delete_entity(self, client, workspace):
        _create_entity(client)
        r = client.delete(f"{BASE}/entities/lead/")
        assert r.status_code == 204
        ent = EntityDefinition.objects.get(workspace_id=workspace.id, slug="lead")
        assert ent.is_active is False
        # excluded from default list
        assert "lead" not in {e["slug"] for e in client.get(f"{BASE}/entities/").data}

    def test_duplicate_entity_rejected(self, client):
        _create_entity(client)
        r = _create_entity(client)
        assert r.status_code == 400


@pytest.mark.django_db
class TestFieldCrud:
    def test_add_and_list_fields(self, client):
        _create_entity(client)
        r = client.post(f"{BASE}/entities/lead/fields/",
                        {"slug": "amount", "name": "Amount", "field_type": "decimal"}, format="json")
        assert r.status_code == 201
        lst = client.get(f"{BASE}/entities/lead/fields/")
        assert "amount" in {f["slug"] for f in lst.data}

    def test_patch_and_delete_field(self, client):
        _create_entity(client)
        client.post(f"{BASE}/entities/lead/fields/",
                    {"slug": "amount", "name": "Amount", "field_type": "decimal"}, format="json")
        p = client.patch(f"{BASE}/entities/lead/fields/amount/", {"name": "Deal Value"}, format="json")
        assert p.status_code == 200 and p.data["name"] == "Deal Value"
        d = client.delete(f"{BASE}/entities/lead/fields/amount/")
        assert d.status_code == 204

    def test_delete_field_is_soft(self, client):
        _create_entity(client)
        client.post(f"{BASE}/entities/lead/fields/",
                    {"slug": "amount", "name": "Amount", "field_type": "decimal"}, format="json")
        d = client.delete(f"{BASE}/entities/lead/fields/amount/")
        assert d.status_code == 204
        # Row persists with is_deleted=True (data preserved), but is hidden from the API.
        fd = FieldDefinition.objects.get(entity__slug="lead", slug="amount")
        assert fd.is_deleted is True
        assert "amount" not in {f["slug"] for f in client.get(f"{BASE}/entities/lead/fields/").data}

    def test_promote_then_demote_field(self, client, workspace):
        _create_entity(client)
        client.post(f"{BASE}/entities/lead/fields/",
                    {"slug": "score", "name": "Score", "field_type": "integer", "is_promoted": False},
                    format="json")
        pr = client.post(f"{BASE}/entities/lead/promote-field/", {"field_slug": "score"}, format="json")
        assert pr.status_code == 200 and pr.data["is_promoted"] is True
        fd = FieldDefinition.objects.get(entity__slug="lead", slug="score")
        assert fd.is_promoted and fd.column_name
        de = client.post(f"{BASE}/entities/lead/demote-field/", {"field_slug": "score"}, format="json")
        assert de.status_code == 200 and de.data["is_promoted"] is False

    def test_promote_already_promoted_rejected(self, client):
        _create_entity(client)
        client.post(f"{BASE}/entities/lead/fields/",
                    {"slug": "score", "name": "Score", "field_type": "integer", "is_promoted": True},
                    format="json")
        r = client.post(f"{BASE}/entities/lead/promote-field/", {"field_slug": "score"}, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestVersionsAndScoping:
    def test_versions_and_rollback(self, client):
        _create_entity(client)
        client.post(f"{BASE}/entities/lead/fields/",
                    {"slug": "amount", "name": "Amount", "field_type": "decimal"}, format="json")
        versions = client.get(f"{BASE}/entities/lead/schema-versions/")
        assert versions.status_code == 200 and len(versions.data) >= 2
        rb = client.post(f"{BASE}/entities/lead/schema-versions/1/rollback/", {}, format="json")
        assert rb.status_code == 200

    def test_no_workspace_header_forbidden(self, user, workspace):
        WorkspaceMember.objects.create(workspace=workspace, user=user, role="admin", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")  # no slug
        r = c.get(f"{BASE}/entities/")
        assert r.status_code == 403

    def test_non_member_forbidden(self, user, workspace):
        c = APIClient()  # user is NOT a member of workspace
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG=workspace.slug)
        r = c.get(f"{BASE}/entities/")
        assert r.status_code == 403

    def test_workspace_isolation(self, client, user):
        # Entity created in 'acme' is invisible from another workspace the user also belongs to.
        _create_entity(client)
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        WorkspaceMember.objects.create(workspace=other, user=user, role="admin", status="active")
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                       HTTP_X_WORKSPACE_SLUG="other")
        assert "lead" not in {e["slug"] for e in c2.get(f"{BASE}/entities/").data}
