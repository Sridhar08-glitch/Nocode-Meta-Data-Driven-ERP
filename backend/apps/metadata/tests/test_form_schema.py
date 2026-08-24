"""
Tests for the Form Schema API (Phase 1.26) — /api/v1/metadata/entities/{slug}/form-schema/
and the authenticated Form Builder CRUD (.../forms/).

Full stack: JWT auth → TenantMiddleware → views → FormSchemaService.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import FormDefinition
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/metadata"


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client_for(workspace, *, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


@pytest.fixture
def client(workspace):
    return _client_for(workspace, role="admin")


def _create_entity(client, slug="lead", name="Lead", plural="Leads", fields=None):
    payload = {"slug": slug, "name": name, "plural_name": plural}
    if fields is not None:
        payload["fields"] = fields
    return client.post(f"{BASE}/entities/", payload, format="json")


_FIELDS = [
    {"slug": "name", "name": "Name", "field_type": "text"},
    {"slug": "email", "name": "Email", "field_type": "email"},
    {"slug": "score", "name": "Score", "field_type": "integer"},
]


@pytest.mark.django_db
class TestFormSchemaResolution:
    def test_synthesised_default_schema_from_fields(self, client):
        _create_entity(client, fields=_FIELDS)
        r = client.get(f"{BASE}/entities/lead/form-schema/")
        assert r.status_code == 200
        assert r.data["entity_slug"] == "lead"
        assert r.data["form_id"] is None
        assert len(r.data["sections"]) == 1
        slugs = r.data["sections"][0]["fields"]
        assert {"name", "email", "score"} <= set(slugs)
        # field payloads present and ordered alongside
        payload_slugs = {f["slug"] for f in r.data["fields"]}
        assert {"name", "email", "score"} <= payload_slugs

    def test_custom_layout_round_trip(self, client):
        _create_entity(client, fields=_FIELDS)
        layout = [{"key": "contact", "title": "Contact", "columns": 2, "fields": ["name", "email"]}]
        cr = client.post(f"{BASE}/entities/lead/forms/",
                         {"name": "Custom", "is_default": True, "layout": layout}, format="json")
        assert cr.status_code == 201
        r = client.get(f"{BASE}/entities/lead/form-schema/")
        assert r.status_code == 200
        assert r.data["form_name"] == "Custom"
        sec = r.data["sections"][0]
        assert sec["title"] == "Contact"
        assert sec["fields"] == ["name", "email"]
        # the unplaced field is appended to a trailing section
        assert any("score" in s["fields"] for s in r.data["sections"])

    def test_readonly_computed_field_marked(self, client):
        _create_entity(client, fields=[
            {"slug": "name", "name": "Name", "field_type": "text"},
            {"slug": "total", "name": "Total", "field_type": "formula",
             "config": {"expression": "1 + 1", "result_type": "integer"}},
        ])
        r = client.get(f"{BASE}/entities/lead/form-schema/")
        total = next(f for f in r.data["fields"] if f["slug"] == "total")
        assert total["is_readonly"] is True

    def test_permission_filtering_hides_unreadable_field(self, workspace):
        admin = _client_for(workspace, role="admin", email="a@example.com")
        _create_entity(admin, fields=[
            {"slug": "name", "name": "Name", "field_type": "text"},
            {"slug": "salary", "name": "Salary", "field_type": "currency",
             "read_roles": ["admin"]},
        ])
        # admin sees salary
        ra = admin.get(f"{BASE}/entities/lead/form-schema/")
        assert "salary" in {f["slug"] for f in ra.data["fields"]}
        # a plain member does not
        member = _client_for(workspace, role="member", email="m@example.com")
        rm = member.get(f"{BASE}/entities/lead/form-schema/")
        slugs = {f["slug"] for f in rm.data["fields"]}
        assert "name" in slugs
        assert "salary" not in slugs
        assert all("salary" not in s["fields"] for s in rm.data["sections"])

    def test_schema_for_unknown_entity_400(self, client):
        r = client.get(f"{BASE}/entities/nope/form-schema/")
        assert r.status_code == 400


@pytest.mark.django_db
class TestFormBuilderCrud:
    def test_create_list_update_delete(self, client):
        _create_entity(client, fields=_FIELDS)
        cr = client.post(f"{BASE}/entities/lead/forms/",
                         {"name": "Intake", "layout": [{"key": "s", "fields": ["name"]}]},
                         format="json")
        assert cr.status_code == 201
        fid = cr.data["id"]

        lr = client.get(f"{BASE}/entities/lead/forms/")
        assert lr.status_code == 200
        assert any(f["id"] == fid for f in lr.data)

        pr = client.patch(f"{BASE}/entities/lead/forms/{fid}/",
                          {"name": "Intake v2"}, format="json")
        assert pr.status_code == 200
        assert pr.data["name"] == "Intake v2"

        dr = client.delete(f"{BASE}/entities/lead/forms/{fid}/")
        assert dr.status_code == 204
        assert not FormDefinition.objects.filter(id=fid).exists()

    def test_set_default_unsets_previous(self, client, workspace):
        _create_entity(client, fields=_FIELDS)
        a = client.post(f"{BASE}/entities/lead/forms/",
                        {"name": "A", "is_default": True}, format="json").data
        b = client.post(f"{BASE}/entities/lead/forms/",
                        {"name": "B", "is_default": True}, format="json").data
        assert FormDefinition.objects.get(id=a["id"]).is_default is False
        assert FormDefinition.objects.get(id=b["id"]).is_default is True

    def test_layout_unknown_field_rejected(self, client):
        _create_entity(client, fields=_FIELDS)
        r = client.post(f"{BASE}/entities/lead/forms/",
                        {"name": "Bad", "layout": [{"key": "s", "fields": ["ghost"]}]},
                        format="json")
        assert r.status_code == 400

    def test_conditional_rule_unknown_field_rejected(self, client):
        _create_entity(client, fields=_FIELDS)
        r = client.post(f"{BASE}/entities/lead/forms/",
                        {"name": "Cond",
                         "settings": {"conditional_rules": [
                             {"field": "ghost", "op": "=", "value": "x", "action": "hide",
                              "target_field": "email"}]}},
                        format="json")
        assert r.status_code == 400

    def test_conditional_rule_valid_accepted(self, client):
        _create_entity(client, fields=_FIELDS)
        r = client.post(f"{BASE}/entities/lead/forms/",
                        {"name": "Cond",
                         "settings": {"conditional_rules": [
                             {"field": "score", "op": ">", "value": 5, "action": "show",
                              "target_field": "email"}]}},
                        format="json")
        assert r.status_code == 201

    def test_viewer_cannot_create_form(self, workspace):
        admin = _client_for(workspace, role="admin", email="a@example.com")
        _create_entity(admin, fields=_FIELDS)
        viewer = _client_for(workspace, role="viewer", email="v@example.com")
        r = viewer.post(f"{BASE}/entities/lead/forms/", {"name": "X"}, format="json")
        assert r.status_code == 403


@pytest.mark.django_db
class TestWorkspaceIsolation:
    def test_cannot_read_other_workspace_form_schema(self, workspace):
        admin = _client_for(workspace, role="admin", email="a@example.com")
        _create_entity(admin, fields=_FIELDS)

        other_ws = Workspace.objects.create(name="Other", slug="other", is_active=True)
        other = _client_for(other_ws, role="admin", email="o@example.com")
        # "lead" does not exist in the other workspace
        r = other.get(f"{BASE}/entities/lead/form-schema/")
        assert r.status_code == 400
