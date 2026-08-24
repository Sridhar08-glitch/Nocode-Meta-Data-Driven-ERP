"""RBAC/ABAC management API (frontend F1.9) — /api/v1/permissions/."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.permissions.models import Role
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/permissions"


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
class TestPermissionsApi:
    def test_role_crud(self, ws):
        c = _client(ws, "admin")
        cr = c.post(f"{BASE}/roles/", {"name": "Manager", "slug": "manager"}, format="json")
        assert cr.status_code == 201
        rid = cr.data["id"]
        assert any(r["slug"] == "manager" for r in c.get(f"{BASE}/roles/").data)
        pr = c.patch(f"{BASE}/roles/{rid}/", {"description": "Mgr"}, format="json")
        assert pr.status_code == 200 and pr.data["description"] == "Mgr"
        assert c.delete(f"{BASE}/roles/{rid}/").status_code == 204

    def test_permission_grant_and_filter_by_role(self, ws):
        c = _client(ws, "admin")
        rid = c.post(f"{BASE}/roles/", {"name": "R", "slug": "r"}, format="json").data["id"]
        gr = c.post(
            f"{BASE}/permissions/",
            {"role": rid, "resource_type": "entity", "action": "read", "is_deny": False,
             "conditions": [{"field": "owner", "op": "=", "value": "$user.id"}]},
            format="json",
        )
        assert gr.status_code == 201
        listed = c.get(f"{BASE}/permissions/?role={rid}").data
        assert len(listed) == 1 and listed[0]["action"] == "read"

    def test_field_permission_and_masking(self, ws):
        c = _client(ws, "admin")
        rid = c.post(f"{BASE}/roles/", {"name": "R", "slug": "r"}, format="json").data["id"]
        fp = c.post(
            f"{BASE}/field-permissions/",
            {"field_id": str(uuid.uuid4()), "role_id": rid, "can_read": False, "can_write": False},
            format="json",
        )
        assert fp.status_code == 201
        mr = c.post(
            f"{BASE}/masking-rules/",
            {"field_id": str(uuid.uuid4()), "role_id": rid, "mask_type": "last_n_chars",
             "mask_pattern": "4"},
            format="json",
        )
        assert mr.status_code == 201

    def test_system_role_not_deletable(self, ws):
        c = _client(ws, "admin")
        sys_role = Role.objects.create(workspace_id=ws.id, name="Owner", slug="owner",
                                       is_system=True)
        assert c.delete(f"{BASE}/roles/{sys_role.id}/").status_code == 400

    def test_member_forbidden(self, ws):
        m = _client(ws, "member", email="m@acme.com")
        assert m.get(f"{BASE}/roles/").status_code == 403
        assert m.post(f"{BASE}/roles/", {"name": "X", "slug": "x"}, format="json").status_code == 403

    def test_cross_workspace_isolation(self, ws):
        c = _client(ws, "admin", email="a@acme.com")
        rid = c.post(f"{BASE}/roles/", {"name": "Secret", "slug": "secret"}, format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc = _client(other, "admin", email="o@other.com")
        assert oc.get(f"{BASE}/roles/{rid}/").status_code == 404
        assert oc.get(f"{BASE}/roles/").data == []
