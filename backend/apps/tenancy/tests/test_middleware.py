import pytest
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from apps.accounts import services as acct_services
from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.middleware import TenantMiddleware
from apps.tenancy.models import Workspace, WorkspaceMember

STRONG_PW = "Sup3rStr0ng!pw"


@pytest.fixture
def mw():
    return TenantMiddleware(get_response=lambda request: HttpResponse())


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="m@example.com", password=STRONG_PW, is_verified=True)


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _bearer(user, workspace_id=None):
    return f"Bearer {tokens.issue_access_token(user, workspace_id)}"


def member(workspace, user, role="member", status="active"):
    return WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status=status)


@pytest.mark.django_db
class TestTenantResolution:
    def test_exempt_path_passes_through(self, mw, rf):
        req = rf.get("/api/v1/auth/login/", HTTP_X_WORKSPACE_SLUG="acme")
        assert mw.process_request(req) is None
        assert req.workspace_id is None

    def test_no_slug_passes_through(self, mw, rf, user):
        req = rf.get("/api/v1/schema/entities/", HTTP_AUTHORIZATION=_bearer(user))
        assert mw.process_request(req) is None
        assert req.workspace_id is None

    def test_unknown_workspace_404(self, mw, rf, user):
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="ghost", HTTP_AUTHORIZATION=_bearer(user))
        resp = mw.process_request(req)
        assert isinstance(resp, JsonResponse) and resp.status_code == 404

    def test_member_resolves_workspace(self, mw, rf, user, workspace):
        member(workspace, user)
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="acme", HTTP_AUTHORIZATION=_bearer(user))
        assert mw.process_request(req) is None
        assert req.workspace_id == workspace.id
        assert req.workspace_member.role == "member"
        # cleanup any RLS GUC set on PostgreSQL
        mw.process_response(req, HttpResponse())

    def test_non_member_403(self, mw, rf, user, workspace):
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="acme", HTTP_AUTHORIZATION=_bearer(user))
        resp = mw.process_request(req)
        assert isinstance(resp, JsonResponse) and resp.status_code == 403
        assert req.workspace_id is None

    def test_suspended_member_403(self, mw, rf, user, workspace):
        member(workspace, user, status="suspended")
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="acme", HTTP_AUTHORIZATION=_bearer(user))
        resp = mw.process_request(req)
        assert resp.status_code == 403

    def test_no_token_with_slug_passes_through(self, mw, rf, workspace):
        # Without a resolvable caller, no workspace context is set (view auth will reject).
        req = rf.get("/api/v1/schema/entities/", HTTP_X_WORKSPACE_SLUG="acme")
        assert mw.process_request(req) is None
        assert req.workspace_id is None

    def test_api_key_member_resolves(self, mw, rf, user, workspace):
        member(workspace, user)
        raw, _ = acct_services.create_api_key(user, "ci", workspace_id=workspace.id)
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="acme", HTTP_X_API_KEY=raw)
        assert mw.process_request(req) is None
        assert req.workspace_id == workspace.id
        mw.process_response(req, HttpResponse())


@pytest.mark.django_db
class TestRlsGuc:
    def test_guc_set_and_reset_on_postgres(self, mw, rf, user, workspace):
        member(workspace, user)
        req = rf.get("/api/v1/schema/entities/",
                     HTTP_X_WORKSPACE_SLUG="acme", HTTP_AUTHORIZATION=_bearer(user))
        mw.process_request(req)
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT current_setting('app.workspace_id', TRUE)")
                assert cur.fetchone()[0] == str(workspace.id)
        mw.process_response(req, HttpResponse())
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT current_setting('app.workspace_id', TRUE)")
                # RESET ⇒ empty string (or None)
                assert cur.fetchone()[0] in ("", None)
