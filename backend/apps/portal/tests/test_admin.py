"""
Custom-admin Portal Builder API (Phase F3.7) — config + portal users + grants.
Owner/admin only; password is hashed + never returned; workspace-scoped.
"""
import pytest
from django.contrib.auth.hashers import check_password
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.portal.models import PortalUser
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/portal-admin"


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


@pytest.mark.django_db
class TestPortalAdmin:
    def test_config_get_or_create_and_update(self, workspace):
        admin, _ = _client(workspace)
        r = admin.get(f"{BASE}/config/")
        assert r.status_code == 200
        r2 = admin.patch(f"{BASE}/config/", {"is_enabled": True, "name": "Client Hub"}, format="json")
        assert r2.status_code == 200
        assert r2.data["is_enabled"] is True
        assert r2.data["name"] == "Client Hub"

    def test_create_portal_user_hashes_password_and_hides_it(self, workspace):
        admin, _ = _client(workspace)
        r = admin.post(f"{BASE}/users/", {
            "email": "Client@Acme.com", "full_name": "Client One", "password": "portalPW123",
            "portal_type": "customer",
        }, format="json")
        assert r.status_code == 201
        assert "password" not in r.data and "password_hash" not in r.data
        assert r.data["email"] == "client@acme.com"  # lower-cased
        pu = PortalUser.objects.get(id=r.data["id"])
        assert pu.is_verified is True
        assert check_password("portalPW123", pu.password_hash)

    def test_create_requires_password(self, workspace):
        admin, _ = _client(workspace)
        r = admin.post(f"{BASE}/users/", {"email": "x@acme.com", "full_name": "X"}, format="json")
        assert r.status_code == 400

    def test_duplicate_portal_user_email_rejected(self, workspace):
        admin, _ = _client(workspace)
        body = {"email": "dup@acme.com", "full_name": "D", "password": "portalPW123"}
        assert admin.post(f"{BASE}/users/", body, format="json").status_code == 201
        assert admin.post(f"{BASE}/users/", body, format="json").status_code == 400

    def test_grant_crud(self, workspace):
        admin, _ = _client(workspace)
        r = admin.post(f"{BASE}/grants/", {
            "entity_slug": "ticket", "portal_type": "customer", "link_field": "customer",
            "can_read": True, "can_create": True,
        }, format="json")
        assert r.status_code == 201
        gid = r.data["id"]
        # duplicate entity+type rejected
        assert admin.post(f"{BASE}/grants/", {"entity_slug": "ticket", "portal_type": "customer", "link_field": "customer"}, format="json").status_code == 400
        assert admin.get(f"{BASE}/grants/").data["count"] == 1
        assert admin.delete(f"{BASE}/grants/{gid}/").status_code == 204

    def test_non_admin_member_forbidden(self, workspace):
        member, _ = _client(workspace, role="member")
        assert member.get(f"{BASE}/users/").status_code == 403
        assert member.get(f"{BASE}/config/").status_code == 403

    def test_workspace_isolation(self, workspace):
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        a, _ = _client(workspace, email="admin1@example.com")
        a.post(f"{BASE}/users/", {"email": "a@acme.com", "full_name": "A", "password": "portalPW123"}, format="json")
        b, _ = _client(other, email="admin2@example.com")
        assert b.get(f"{BASE}/users/").data["count"] == 0
