"""Email templates (Phase 1.33) — render/sanitize, versioning, test-send, CRUD, isolation."""
import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.email_templates.models import EmailTemplate
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/templates/email"


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
    return c


@pytest.mark.django_db
class TestEmailTemplates:
    def test_create_render_sanitizes_and_substitutes(self, ws):
        c = _client(ws, "admin")
        cr = c.post(f"{BASE}/", {
            "name": "Welcome", "slug": "welcome",
            "subject_template": "Hi ${name}",
            "body_html": "<p>Hello ${name}</p><script>alert(1)</script>"},
            format="json")
        assert cr.status_code == 201
        tid = cr.data["id"]
        r = c.post(f"{BASE}/{tid}/render/", {"context": {"name": "Pat"}}, format="json")
        assert r.data["subject"] == "Hi Pat"
        assert "Hello Pat" in r.data["html"]
        assert "<script" not in r.data["html"].lower()

    def test_version_bumps_on_content_change(self, ws):
        c = _client(ws, "admin")
        tid = c.post(f"{BASE}/", {"name": "T", "slug": "t", "body_html": "<p>v1</p>"},
                     format="json").data["id"]
        assert EmailTemplate.objects.get(id=tid).version == 1
        c.patch(f"{BASE}/{tid}/", {"body_html": "<p>v2</p>"}, format="json")
        assert EmailTemplate.objects.get(id=tid).version == 2
        # a non-content change does not bump
        c.patch(f"{BASE}/{tid}/", {"name": "T renamed"}, format="json")
        assert EmailTemplate.objects.get(id=tid).version == 2

    def test_test_send_uses_outbox(self, ws):
        c = _client(ws, "admin")
        tid = c.post(f"{BASE}/", {"name": "T", "slug": "t",
                                  "subject_template": "Hello ${name}",
                                  "body_html": "<p>Hi ${name}</p>"}, format="json").data["id"]
        mail.outbox.clear()
        r = c.post(f"{BASE}/{tid}/test-send/",
                   {"to_email": "dest@example.com", "context": {"name": "Sam"}}, format="json")
        assert r.status_code == 200 and r.data["sent"] is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Hello Sam"
        assert mail.outbox[0].to == ["dest@example.com"]

    def test_test_send_requires_recipient(self, ws):
        c = _client(ws, "admin")
        tid = c.post(f"{BASE}/", {"name": "T", "slug": "t"}, format="json").data["id"]
        assert c.post(f"{BASE}/{tid}/test-send/", {}, format="json").status_code == 400

    def test_slug_locale_uniqueness(self, ws):
        c = _client(ws, "admin")
        c.post(f"{BASE}/", {"name": "T", "slug": "t", "locale": "en"}, format="json")
        # same slug+locale → 400
        assert c.post(f"{BASE}/", {"name": "T", "slug": "t", "locale": "en"},
                      format="json").status_code == 400
        # same slug, different locale → ok
        assert c.post(f"{BASE}/", {"name": "T fr", "slug": "t", "locale": "fr"},
                      format="json").status_code == 201

    def test_member_cannot_edit(self, ws):
        _client(ws, "admin", email="a@acme.com").post(
            f"{BASE}/", {"name": "T", "slug": "t"}, format="json")
        member = _client(ws, "member", email="m@acme.com")
        assert member.get(f"{BASE}/").status_code == 200
        assert member.post(f"{BASE}/", {"name": "X", "slug": "x"},
                           format="json").status_code == 403

    def test_cross_workspace_isolation(self, ws):
        a = _client(ws, "admin", email="a@acme.com")
        tid = a.post(f"{BASE}/", {"name": "T", "slug": "secret"}, format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc = _client(other, "admin", email="o@other.com")
        assert oc.get(f"{BASE}/{tid}/").status_code == 404
        assert oc.get(f"{BASE}/").data["count"] == 0
