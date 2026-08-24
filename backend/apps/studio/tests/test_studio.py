"""
Studio (Phase 1.32) — Applications / Home Layouts / Navigation: CRUD + publish,
app-switcher gating, home-layout resolution precedence, nav permission filtering,
and workspace isolation.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.studio import services
from apps.studio.models import Application, HomeLayout, Navigation
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
APPS = "/api/v1/applications"
HOME = "/api/v1/home-layouts"
NAV = "/api/v1/navigation"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(ws, role="admin", email=None):
    email = email or f"{role}@acme.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c, user


# ── Applications ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestApplications:
    def test_crud_and_publish_then_switcher(self, ws):
        admin, _ = _client(ws, "admin")
        cr = admin.post(f"{APPS}/", {"name": "CRM", "slug": "crm"}, format="json")
        assert cr.status_code == 201
        aid = cr.data["id"]
        # draft → not in switcher
        assert admin.get(f"{APPS}/switcher/").data["count"] == 0
        pub = admin.post(f"{APPS}/{aid}/publish/")
        assert pub.status_code == 200 and pub.data["is_published"] is True
        sw = admin.get(f"{APPS}/switcher/")
        assert sw.data["count"] == 1 and sw.data["results"][0]["slug"] == "crm"

    def test_duplicate_slug_rejected(self, ws):
        admin, _ = _client(ws, "admin")
        admin.post(f"{APPS}/", {"name": "A", "slug": "dup"}, format="json")
        r = admin.post(f"{APPS}/", {"name": "B", "slug": "dup"}, format="json")
        assert r.status_code == 400

    def test_member_cannot_edit_but_can_read(self, ws):
        admin, _ = _client(ws, "admin", email="a@acme.com")
        admin.post(f"{APPS}/", {"name": "CRM", "slug": "crm"}, format="json")
        member, _ = _client(ws, "member", email="m@acme.com")
        assert member.get(f"{APPS}/").status_code == 200
        assert member.post(f"{APPS}/", {"name": "X", "slug": "x"}, format="json").status_code == 403

    def test_switcher_role_gating(self, ws):
        admin, _ = _client(ws, "admin", email="a@acme.com")
        # app restricted to "admin" role only
        a = Application.objects.create(workspace_id=ws.id, name="Ops", slug="ops",
                                       role_ids=["admin"], is_published=True)
        assert a.id
        viewer, _ = _client(ws, "viewer", email="v@acme.com")
        assert viewer.get(f"{APPS}/switcher/").data["count"] == 0     # viewer excluded
        assert admin.get(f"{APPS}/switcher/").data["count"] == 1      # admin allowed


# ── Home layouts ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestHomeLayoutResolution:
    def test_precedence_personal_over_role_over_workspace(self, ws):
        admin, user = _client(ws, "admin")
        HomeLayout.objects.create(workspace_id=ws.id, name="WS", scope="workspace",
                                  widgets=[{"k": "ws"}], is_published=True)
        # resolve → workspace (only one so far)
        r = admin.get(f"{HOME}/resolve/")
        assert r.data["widgets"] == [{"k": "ws"}]
        # add a personal layout for this user → wins
        HomeLayout.objects.create(workspace_id=ws.id, name="Mine", scope="personal",
                                  target_id=user.id, widgets=[{"k": "me"}], is_published=True)
        r = admin.get(f"{HOME}/resolve/")
        assert r.data["widgets"] == [{"k": "me"}]

    def test_draft_layout_not_resolved(self, ws):
        admin, _ = _client(ws, "admin")
        HomeLayout.objects.create(workspace_id=ws.id, name="WS", scope="workspace",
                                  widgets=[{"k": "ws"}], is_published=False)
        assert admin.get(f"{HOME}/resolve/").data == {}

    def test_scope_target_validation(self, ws):
        admin, _ = _client(ws, "admin")
        r = admin.post(f"{HOME}/", {"name": "bad", "scope": "role"}, format="json")
        assert r.status_code == 400   # role scope requires target_id

    def test_resolve_service_role_layout(self, ws):
        role_id = uuid.uuid4()
        HomeLayout.objects.create(workspace_id=ws.id, name="R", scope="role",
                                  target_id=role_id, widgets=[{"k": "role"}], is_published=True)
        HomeLayout.objects.create(workspace_id=ws.id, name="W", scope="workspace",
                                  widgets=[{"k": "ws"}], is_published=True)
        got = services.resolve_home_layout(workspace_id=ws.id, role_ids=[role_id])
        assert got.widgets == [{"k": "role"}]


# ── Navigation ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestNavigation:
    def test_resolve_filters_items_by_role(self, ws):
        Navigation.objects.create(
            workspace_id=ws.id, name="Main", scope="workspace", is_published=True,
            tree=[{"label": "Sales", "items": [
                {"label": "Leads", "target": "lead"},
                {"label": "Admin Panel", "target": "admin", "roles": ["admin"]},
            ]}])
        admin, _ = _client(ws, "admin", email="a@acme.com")
        member, _ = _client(ws, "member", email="m@acme.com")
        admin_items = [i["label"] for i in admin.get(f"{NAV}/resolve/").data["groups"][0]["items"]]
        member_items = [i["label"] for i in member.get(f"{NAV}/resolve/").data["groups"][0]["items"]]
        assert "Admin Panel" in admin_items
        assert "Admin Panel" not in member_items
        assert "Leads" in member_items

    def test_app_nav_overrides_workspace(self, ws):
        admin, _ = _client(ws, "admin")
        app_id = uuid.uuid4()
        Navigation.objects.create(workspace_id=ws.id, name="WS", scope="workspace",
                                  is_published=True, tree=[{"label": "WSGroup", "items": []}])
        Navigation.objects.create(workspace_id=ws.id, name="App", scope="app",
                                  target_id=app_id, is_published=True,
                                  tree=[{"label": "AppGroup", "items": []}])
        r = admin.get(f"{NAV}/resolve/?app={app_id}")
        assert r.data["groups"][0]["label"] == "AppGroup"

    def test_group_dropped_when_all_items_filtered(self, ws):
        admin, _ = _client(ws, "admin", email="a@acme.com")
        Navigation.objects.create(
            workspace_id=ws.id, name="Main", scope="workspace", is_published=True,
            tree=[{"label": "AdminOnly", "items": [
                {"label": "X", "target": "x", "roles": ["admin"]}]}])
        member, _ = _client(ws, "member", email="m@acme.com")
        assert member.get(f"{NAV}/resolve/").data["groups"] == []


# ── isolation ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestIsolation:
    def test_application_cross_workspace(self, ws):
        admin, _ = _client(ws, "admin", email="a@acme.com")
        aid = admin.post(f"{APPS}/", {"name": "CRM", "slug": "crm"}, format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc, _ = _client(other, "admin", email="o@other.com")
        assert oc.get(f"{APPS}/{aid}/").status_code == 404
        assert oc.get(f"{APPS}/").data["count"] == 0
