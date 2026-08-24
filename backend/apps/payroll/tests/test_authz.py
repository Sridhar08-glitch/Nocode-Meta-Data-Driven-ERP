"""Overtime creation must be role-gated (P2.17) — it was the only payroll write
endpoint left ungated while every other payroll mutation requires admin."""
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
class TestPayrollOvertimeAuthz:
    def _ws(self):
        return Workspace.objects.create(name="Pay", slug="pay", is_active=True)

    def test_viewer_cannot_create_overtime(self, db):
        r = _client(self._ws(), "viewer", "v@pay.com").post(
            "/api/v1/payroll/overtime/",
            {"employee_record_id": str(uuid.uuid4()), "hours": 2, "rate": 50}, format="json")
        assert r.status_code == 403

    def test_member_cannot_create_overtime(self, db):
        r = _client(self._ws(), "member", "m@pay.com").post(
            "/api/v1/payroll/overtime/",
            {"employee_record_id": str(uuid.uuid4()), "hours": 2, "rate": 50}, format="json")
        assert r.status_code == 403
