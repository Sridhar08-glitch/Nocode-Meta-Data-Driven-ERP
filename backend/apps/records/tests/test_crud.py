"""
Full-stack tests for the auto-generated CRUD API + RBAC/ABAC — the security-
critical surface (PROJECT_HANDBOOK.md §15 / master §13). Every request runs through real
JWT auth → TenantMiddleware (membership + RLS) → RBAC → ABAC → NQL → masking.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.permissions.models import DataMaskingRule, Permission, Role
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/data/lead"


def _client(workspace, email, role="admin", custom_role_id=None):
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role,
                                   status="active", custom_role_id=custom_role_id)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return user, c


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def admin(workspace):
    return _client(workspace, "admin@acme.com", role="admin")


@pytest.fixture
def lead(workspace):
    ent = SchemaRegistryService.create_entity(
        workspace_id=workspace.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead",
                                    slug="name", name="Name", field_type="text",
                                    is_promoted=True, is_required=True)
    SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead",
                                    slug="value", name="Value", field_type="decimal", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead",
                                    slug="owner", name="Owner", field_type="user", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=workspace.id, entity_slug="lead",
                                    slug="notes", name="Notes", field_type="text", is_promoted=False)
    ent.refresh_from_db()
    return ent


@pytest.mark.django_db
class TestCrudLifecycle:
    def test_create_list_retrieve_update_delete_restore(self, admin, lead):
        _, c = admin
        # create (note overflow field 'notes')
        r = c.post(f"{BASE}/", {"name": "Acme", "value": 1000, "notes": "hi"}, format="json")
        assert r.status_code == 201
        rid = r.data["id"]
        assert r.data["name"] == "Acme" and r.data["notes"] == "hi"
        # list
        lst = c.get(f"{BASE}/")
        assert lst.status_code == 200 and lst.data["count"] == 1
        # retrieve
        assert c.get(f"{BASE}/{rid}/").status_code == 200
        # update
        up = c.patch(f"{BASE}/{rid}/", {"value": 2500}, format="json")
        assert up.status_code == 200 and int(up.data["value"]) == 2500
        # delete (soft)
        assert c.delete(f"{BASE}/{rid}/").status_code == 204
        assert c.get(f"{BASE}/{rid}/").status_code == 404
        assert c.get(f"{BASE}/").data["count"] == 0
        # restore
        assert c.post(f"{BASE}/{rid}/restore/").status_code == 200
        assert c.get(f"{BASE}/{rid}/").status_code == 200

    def test_validation(self, admin, lead):
        _, c = admin
        assert c.post(f"{BASE}/", {"value": 1}, format="json").status_code == 400         # missing required name
        assert c.post(f"{BASE}/", {"name": "x", "nope": 1}, format="json").status_code == 400  # unknown field

    def test_filter_and_sort(self, admin, lead):
        _, c = admin
        c.post(f"{BASE}/", {"name": "A", "value": 100}, format="json")
        c.post(f"{BASE}/", {"name": "B", "value": 900}, format="json")
        import json
        flt = json.dumps({"op": "and", "conditions": [{"field": "value", "op": ">=", "value": 500}]})
        r = c.get(f"{BASE}/", {"filter": flt, "sort": "-value"})
        assert r.data["count"] == 1 and r.data["results"][0]["name"] == "B"


@pytest.mark.django_db
class TestRBAC:
    def test_viewer_cannot_create_but_can_read(self, admin, workspace, lead):
        _, ac = admin
        ac.post(f"{BASE}/", {"name": "A", "value": 1}, format="json")
        _, vc = _client(workspace, "viewer@acme.com", role="viewer")
        assert vc.post(f"{BASE}/", {"name": "B", "value": 2}, format="json").status_code == 403
        assert vc.get(f"{BASE}/").status_code == 200

    def test_non_member_forbidden(self, workspace, lead):
        user = User.objects.create_user(email="out@x.com", password=PW, is_verified=True)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG="acme")
        assert c.get(f"{BASE}/").status_code == 403   # TenantMiddleware blocks non-members


@pytest.mark.django_db
class TestABAC:
    def test_own_records_only(self, admin, workspace, lead):
        _, ac = admin
        # own-only read role
        role = Role.objects.create(workspace_id=workspace.id, name="OwnOnly", slug="ownonly")
        Permission.objects.create(role=role, workspace_id=workspace.id, resource_type="entity",
                                  resource_id=lead.id, action="read",
                                  conditions=[{"field": "owner", "op": "=", "value": "$user.id"}])
        u, c = _client(workspace, "rep@acme.com", role="member", custom_role_id=role.id)
        other = uuid.uuid4()
        mine = ac.post(f"{BASE}/", {"name": "Mine", "value": 1, "owner": str(u.id)}, format="json").data
        ac.post(f"{BASE}/", {"name": "Theirs", "value": 1, "owner": str(other)}, format="json")
        # list scoped to my records only
        rows = c.get(f"{BASE}/").data["results"]
        assert len(rows) == 1 and rows[0]["name"] == "Mine"
        # retrieving someone else's record is forbidden
        theirs_id = ac.get(f"{BASE}/").data["results"]
        their_rid = next(r["id"] for r in theirs_id if r["name"] == "Theirs")
        assert c.get(f"{BASE}/{their_rid}/").status_code == 403
        assert c.get(f"{BASE}/{mine['id']}/").status_code == 200


@pytest.mark.django_db
class TestMasking:
    def test_field_masked_for_role(self, admin, workspace, lead):
        _, ac = admin
        rid = ac.post(f"{BASE}/", {"name": "A", "value": 9999}, format="json").data["id"]
        role = Role.objects.create(workspace_id=workspace.id, name="Masked", slug="masked")
        # a masking role must first be granted read on the entity (scoped custom roles
        # are governed solely by their grants — no permissive member fallback)
        Permission.objects.create(role=role, workspace_id=workspace.id, resource_type="entity",
                                  resource_id=lead.id, action="read")
        value_fd = lead.fields.get(slug="value")
        DataMaskingRule.objects.create(workspace_id=workspace.id, field_id=value_fd.id,
                                       role_id=role.id, mask_type="full", mask_pattern="")
        _, c = _client(workspace, "masked@acme.com", role="member", custom_role_id=role.id)
        rec = c.get(f"{BASE}/{rid}/").data
        assert rec["value"] != 9999 and str(rec["value"]).startswith("*")
