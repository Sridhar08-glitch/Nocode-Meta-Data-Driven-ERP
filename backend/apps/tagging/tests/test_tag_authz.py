"""Tag mutations require a write role — a viewer (read-only) cannot tag (P2.17 authz)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _client(ws, role, email):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=u, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.mark.django_db
class TestTagAuthz:
    def test_viewer_cannot_create_tag(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        r = _client(ws, "viewer", "v@acme.com").post(
            "/api/v1/tags/", {"name": "VIP", "slug": "vip"}, format="json")
        assert r.status_code == 403

    def test_member_can_create_tag(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        r = _client(ws, "member", "m@acme.com").post(
            "/api/v1/tags/", {"name": "VIP", "slug": "vip"}, format="json")
        assert r.status_code == 201

    def test_viewer_cannot_detach(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        r = _client(ws, "viewer", "v2@acme.com").delete(
            "/api/v1/tags/records/", {"tag_id": "x", "record_id": "y"}, format="json")
        assert r.status_code == 403
