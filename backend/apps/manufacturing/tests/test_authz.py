"""Quality-check / NCR creation must be role-gated (P2.17 authz hardening) —
previously any active member (incl. a read-only viewer) could post them."""
import uuid

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
class TestManufacturingAuthz:
    def _ws(self):
        return Workspace.objects.create(name="Mfg", slug="mfg", is_active=True)

    def test_viewer_cannot_create_quality_check(self, db):
        r = _client(self._ws(), "viewer", "v@mfg.com").post(
            "/api/v1/manufacturing/quality-checks/",
            {"production_order_id": str(uuid.uuid4())}, format="json")
        assert r.status_code == 403

    def test_member_cannot_create_quality_check(self, db):
        r = _client(self._ws(), "member", "m@mfg.com").post(
            "/api/v1/manufacturing/quality-checks/",
            {"production_order_id": str(uuid.uuid4())}, format="json")
        assert r.status_code == 403

    def test_viewer_cannot_create_ncr(self, db):
        r = _client(self._ws(), "viewer", "v2@mfg.com").post(
            "/api/v1/manufacturing/ncrs/",
            {"production_order_id": str(uuid.uuid4()), "defect": "x"}, format="json")
        assert r.status_code == 403
