"""GET /api/v1/workspaces/ — the authenticated user's active workspaces (F1.4 support)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
URL = "/api/v1/workspaces/"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@example.com", password=PW, is_verified=True)


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
    return c


@pytest.mark.django_db
class TestMyWorkspaces:
    def test_lists_active_memberships_with_role_and_limits(self, user):
        a = Workspace.objects.create(name="Acme", slug="acme", is_active=True, plan="pro",
                                     max_entities=50)
        b = Workspace.objects.create(name="Beta", slug="beta", is_active=True)
        WorkspaceMember.objects.create(workspace=a, user=user, role="admin", status="active")
        WorkspaceMember.objects.create(workspace=b, user=user, role="viewer", status="active")

        r = _client(user).get(URL)
        assert r.status_code == 200
        by_slug = {w["slug"]: w for w in r.data}
        assert by_slug["acme"]["role"] == "admin"
        assert by_slug["acme"]["plan"] == "pro"
        assert by_slug["acme"]["limits"]["max_entities"] == 50
        assert by_slug["beta"]["role"] == "viewer"

    def test_excludes_non_active_membership(self, user):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        WorkspaceMember.objects.create(workspace=ws, user=user, role="member", status="invited")
        assert _client(user).get(URL).data == []

    def test_excludes_inactive_workspace(self, user):
        ws = Workspace.objects.create(name="Dead", slug="dead", is_active=False)
        WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")
        assert _client(user).get(URL).data == []

    def test_only_my_workspaces(self, user):
        other = User.objects.create_user(email="o@example.com", password=PW, is_verified=True)
        ws = Workspace.objects.create(name="Theirs", slug="theirs", is_active=True)
        WorkspaceMember.objects.create(workspace=ws, user=other, role="admin", status="active")
        assert _client(user).get(URL).data == []

    def test_requires_auth(self):
        assert APIClient().get(URL).status_code in (401, 403)
