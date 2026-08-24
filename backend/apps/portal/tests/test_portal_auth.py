import pytest
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import tokens as acct_tokens
from apps.accounts.models import User
from apps.portal.models import PortalSession, PortalUser
from apps.tenancy.models import Workspace

PW = "P0rtalStr0ng!pw"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def portal_user(workspace):
    return PortalUser.objects.create(
        workspace_id=workspace.id, email="cust@acme.com", full_name="Cust",
        password_hash=make_password(PW), is_active=True, is_verified=True,
    )


@pytest.mark.django_db
class TestPortalLogin:
    def test_login_success(self, api, workspace, portal_user):
        r = api.post(reverse("portal:login"),
                     {"workspace_slug": "acme", "email": portal_user.email, "password": PW}, format="json")
        assert r.status_code == 200
        assert "access" in r.data and "refresh" in r.data
        assert r.data["portal_user"]["workspace_id"] == str(workspace.id)

    def test_login_wrong_password(self, api, portal_user):
        r = api.post(reverse("portal:login"),
                     {"workspace_slug": "acme", "email": portal_user.email, "password": "nope!"}, format="json")
        assert r.status_code == 401

    def test_login_unknown_workspace(self, api, portal_user):
        r = api.post(reverse("portal:login"),
                     {"workspace_slug": "ghost", "email": portal_user.email, "password": PW}, format="json")
        assert r.status_code == 401

    def test_login_unverified(self, api, workspace):
        PortalUser.objects.create(workspace_id=workspace.id, email="u@acme.com",
                                  full_name="U", password_hash=make_password(PW),
                                  is_active=True, is_verified=False)
        r = api.post(reverse("portal:login"),
                     {"workspace_slug": "acme", "email": "u@acme.com", "password": PW}, format="json")
        assert r.status_code == 403


@pytest.mark.django_db
class TestPortalRealm:
    def _login(self, api, portal_user):
        return api.post(reverse("portal:login"),
                        {"workspace_slug": "acme", "email": portal_user.email, "password": PW},
                        format="json").data

    def test_me_with_portal_token(self, api, portal_user):
        data = self._login(api, portal_user)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        r = api.get(reverse("portal:me"))
        assert r.status_code == 200
        assert r.data["realm"] == "portal"

    def test_workspace_token_rejected_by_portal(self, api, db, portal_user):
        wuser = User.objects.create_user(email="w@example.com", password=PW, is_verified=True)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {acct_tokens.issue_access_token(wuser)}")
        r = api.get(reverse("portal:me"))
        assert r.status_code in (401, 403)

    def test_portal_token_rejected_by_workspace(self, api, portal_user):
        data = self._login(api, portal_user)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        # accounts logout requires a workspace token; a portal token must not work
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)

    def test_refresh_rotation_and_reuse(self, api, portal_user):
        data = self._login(api, portal_user)
        refresh = data["refresh"]
        r1 = api.post(reverse("portal:refresh"), {"refresh": refresh}, format="json")
        assert r1.status_code == 200 and r1.data["refresh"] != refresh
        # Reusing the now-stale token revokes the session
        r2 = api.post(reverse("portal:refresh"), {"refresh": refresh}, format="json")
        assert r2.status_code == 401
        session = PortalSession.objects.filter(portal_user_id=portal_user.id).latest("created_at")
        assert not session.is_active
