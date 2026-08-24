"""
Workspace & Identity Administration API (P2.17 readiness remediation).

Covers the lifecycle that closes GAP-1..8: self-service workspace creation,
member add/role/suspend/remove, ownership transfer, admin password reset, plus
permission gating and last-owner protections.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import PasswordResetToken, User
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
URL = "/api/v1/workspaces/"


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
    return c


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="owner@example.com", password=PW, is_verified=True)


def _make_ws(owner_user, *, slug="acme", name="Acme", **kw):
    ws = Workspace.objects.create(name=name, slug=slug, is_active=True, owner=owner_user, **kw)
    WorkspaceMember.objects.create(workspace=ws, user=owner_user, role="owner", status="active")
    return ws


@pytest.mark.django_db
class TestOnboarding:
    def test_brand_new_user_can_create_workspace_and_becomes_owner(self, owner):
        r = _client(owner).post(URL, {"name": "Nexus MTG"}, format="json")
        assert r.status_code == 201, r.data
        assert r.data["slug"] == "nexus-mtg"
        assert r.data["role"] == "owner"
        m = WorkspaceMember.objects.get(workspace_id=r.data["id"], user=owner)
        assert m.role == "owner" and m.status == "active"
        # It now shows up in the membership listing (the journey is unblocked).
        listing = _client(owner).get(URL)
        assert any(w["slug"] == "nexus-mtg" for w in listing.data)

    def test_slug_collision_is_disambiguated(self, owner):
        _client(owner).post(URL, {"name": "Acme"}, format="json")
        r = _client(owner).post(URL, {"name": "Acme"}, format="json")
        assert r.status_code == 201
        assert r.data["slug"] == "acme-2"

    def test_blank_name_rejected(self, owner):
        r = _client(owner).post(URL, {"name": "   "}, format="json")
        assert r.status_code == 400

    def test_create_requires_auth(self):
        assert APIClient().post(URL, {"name": "x"}, format="json").status_code in (401, 403)


@pytest.mark.django_db
class TestMembers:
    def test_admin_adds_new_user_creates_account_and_set_password_link(self, owner):
        ws = _make_ws(owner)
        r = _client(owner).post(f"{URL}{ws.slug}/members/",
                                {"email": "new@example.com", "full_name": "New Hire",
                                 "role": "member"}, format="json")
        assert r.status_code == 201, r.data
        assert r.data["created_user"] is True
        assert r.data["role"] == "member" and r.data["status"] == "active"
        new_user = User.objects.get(email="new@example.com")
        assert new_user.is_verified and not new_user.has_usable_password()
        # a set-password (reset) token was minted so they can sign in
        assert PasswordResetToken.objects.filter(user=new_user).exists()

    def test_add_existing_user_does_not_recreate(self, owner):
        ws = _make_ws(owner)
        existing = User.objects.create_user(email="e@example.com", password=PW, is_verified=True)
        r = _client(owner).post(f"{URL}{ws.slug}/members/",
                                {"email": "e@example.com", "role": "admin"}, format="json")
        assert r.status_code == 201
        assert r.data["created_user"] is False
        assert User.objects.filter(email="e@example.com").count() == 1
        assert WorkspaceMember.objects.get(workspace=ws, user=existing).role == "admin"

    def test_duplicate_active_member_rejected(self, owner):
        ws = _make_ws(owner)
        _client(owner).post(f"{URL}{ws.slug}/members/",
                            {"email": "d@example.com"}, format="json")
        r = _client(owner).post(f"{URL}{ws.slug}/members/",
                                {"email": "d@example.com"}, format="json")
        assert r.status_code == 400

    def test_member_limit_enforced(self, owner):
        ws = _make_ws(owner, max_members=1)  # owner already fills the single seat
        r = _client(owner).post(f"{URL}{ws.slug}/members/",
                                {"email": "x@example.com"}, format="json")
        assert r.status_code == 400
        assert "limit" in r.data["detail"].lower()

    def test_list_members(self, owner):
        ws = _make_ws(owner)
        _client(owner).post(f"{URL}{ws.slug}/members/", {"email": "a@example.com"}, format="json")
        r = _client(owner).get(f"{URL}{ws.slug}/members/")
        assert r.status_code == 200
        emails = {m["email"] for m in r.data}
        assert {"owner@example.com", "a@example.com"} <= emails

    def test_assign_role_and_reject_owner_via_role(self, owner):
        ws = _make_ws(owner)
        add = _client(owner).post(f"{URL}{ws.slug}/members/",
                                  {"email": "r@example.com", "role": "member"}, format="json")
        mid = add.data["id"]
        r = _client(owner).patch(f"{URL}{ws.slug}/members/{mid}/", {"role": "admin"}, format="json")
        assert r.status_code == 200 and r.data["role"] == "admin"
        r = _client(owner).patch(f"{URL}{ws.slug}/members/{mid}/", {"role": "owner"}, format="json")
        assert r.status_code == 400  # owner only via transfer-ownership

    def test_suspend_and_reactivate(self, owner):
        ws = _make_ws(owner)
        mid = _client(owner).post(f"{URL}{ws.slug}/members/",
                                  {"email": "s@example.com"}, format="json").data["id"]
        r = _client(owner).post(f"{URL}{ws.slug}/members/{mid}/suspend/")
        assert r.status_code == 200 and r.data["status"] == "suspended"
        r = _client(owner).post(f"{URL}{ws.slug}/members/{mid}/reactivate/")
        assert r.status_code == 200 and r.data["status"] == "active"

    def test_remove_member_and_cannot_remove_owner(self, owner):
        ws = _make_ws(owner)
        mid = _client(owner).post(f"{URL}{ws.slug}/members/",
                                  {"email": "g@example.com"}, format="json").data["id"]
        assert _client(owner).delete(f"{URL}{ws.slug}/members/{mid}/").status_code == 204
        owner_mid = str(WorkspaceMember.objects.get(workspace=ws, user=owner).id)
        assert _client(owner).delete(f"{URL}{ws.slug}/members/{owner_mid}/").status_code == 400

    def test_admin_reset_password_sends_link(self, owner):
        ws = _make_ws(owner)
        target = User.objects.create_user(email="t@example.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=target, role="member", status="active")
        mid = str(WorkspaceMember.objects.get(workspace=ws, user=target).id)
        before = PasswordResetToken.objects.filter(user=target).count()
        r = _client(owner).post(f"{URL}{ws.slug}/members/{mid}/reset-password/")
        assert r.status_code == 200
        assert PasswordResetToken.objects.filter(user=target).count() == before + 1


@pytest.mark.django_db
class TestOwnershipAndSettings:
    def test_transfer_ownership_demotes_old_owner(self, owner):
        ws = _make_ws(owner)
        mid = _client(owner).post(f"{URL}{ws.slug}/members/",
                                  {"email": "heir@example.com", "role": "admin"},
                                  format="json").data["id"]
        r = _client(owner).post(f"{URL}{ws.slug}/transfer-ownership/",
                                {"member_id": mid}, format="json")
        assert r.status_code == 200 and r.data["role"] == "owner"
        ws.refresh_from_db()
        assert str(ws.owner_id) == str(User.objects.get(email="heir@example.com").id)
        assert WorkspaceMember.objects.get(workspace=ws, user=owner).role == "admin"

    def test_update_workspace_settings(self, owner):
        ws = _make_ws(owner)
        r = _client(owner).patch(f"{URL}{ws.slug}/",
                                 {"name": "Acme Inc", "plan": "pro", "max_members": 25},
                                 format="json")
        assert r.status_code == 200
        ws.refresh_from_db()
        assert ws.name == "Acme Inc" and ws.plan == "pro" and ws.max_members == 25


@pytest.mark.django_db
class TestPermissionGating:
    def _seat(self, owner, role):
        ws = _make_ws(owner)
        u = User.objects.create_user(email=f"{role}@example.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=u, role=role, status="active")
        return ws, u

    def test_plain_member_cannot_add(self, owner):
        ws, member = self._seat(owner, "member")
        r = _client(member).post(f"{URL}{ws.slug}/members/",
                                 {"email": "z@example.com"}, format="json")
        assert r.status_code == 403

    def test_admin_cannot_transfer_ownership(self, owner):
        ws, admin = self._seat(owner, "admin")
        owner_mid = str(WorkspaceMember.objects.get(workspace=ws, user=admin).id)
        r = _client(admin).post(f"{URL}{ws.slug}/transfer-ownership/",
                                {"member_id": owner_mid}, format="json")
        assert r.status_code == 403

    def test_non_member_gets_403(self, owner):
        ws = _make_ws(owner)
        outsider = User.objects.create_user(email="out@example.com", password=PW, is_verified=True)
        assert _client(outsider).get(f"{URL}{ws.slug}/members/").status_code == 403

    def test_unknown_workspace_404(self, owner):
        assert _client(owner).get(f"{URL}nope/members/").status_code == 404
