"""Business Rules management API (frontend F2.4) — /api/v1/rules/."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.rules.models import BusinessRule
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/rules"


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


def _rule(eid):
    return {"name": "Block", "slug": "block", "entity_id": str(eid), "trigger_on": "before_create",
            "condition_nql": "", "actions": [{"type": "block_save"}]}


@pytest.mark.django_db
class TestRulesApi:
    def test_crud(self, ws):
        c = _client(ws, "admin")
        eid = uuid.uuid4()
        cr = c.post(f"{BASE}/", _rule(eid), format="json")
        assert cr.status_code == 201
        rid = cr.data["id"]
        assert c.get(f"{BASE}/").data["count"] == 1
        assert c.get(f"{BASE}/?entity_id={eid}").data["count"] == 1
        pr = c.patch(f"{BASE}/{rid}/", {"is_active": False}, format="json")
        assert pr.status_code == 200 and pr.data["is_active"] is False
        assert c.delete(f"{BASE}/{rid}/").status_code == 204
        assert BusinessRule.objects.filter(id=rid).count() == 0

    def test_duplicate_slug_rejected(self, ws):
        c = _client(ws, "admin")
        eid = uuid.uuid4()
        c.post(f"{BASE}/", _rule(eid), format="json")
        assert c.post(f"{BASE}/", _rule(eid), format="json").status_code == 400

    def test_member_cannot_write_but_can_read(self, ws):
        _client(ws, "admin", email="a@acme.com").post(f"{BASE}/", _rule(uuid.uuid4()), format="json")
        m = _client(ws, "member", email="m@acme.com")
        assert m.get(f"{BASE}/").status_code == 200
        assert m.post(f"{BASE}/", _rule(uuid.uuid4()), format="json").status_code == 403

    def test_cross_workspace_isolation(self, ws):
        c = _client(ws, "admin", email="a@acme.com")
        rid = c.post(f"{BASE}/", _rule(uuid.uuid4()), format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc = _client(other, "admin", email="o@other.com")
        assert oc.get(f"{BASE}/{rid}/").status_code == 404
        assert oc.get(f"{BASE}/").data["count"] == 0
