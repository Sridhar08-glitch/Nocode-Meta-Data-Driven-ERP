"""Tenant-health metrics (Phase 1.31) — /api/v1/admin/health/."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/admin"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(ws, role="admin", email=None):
    email = email or f"{role}@acme.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c, user, member


@pytest.mark.django_db
class TestHealth:
    def test_admin_gets_metrics_shape(self, ws):
        c, _, _ = _client(ws, "admin")
        r = c.get(f"{BASE}/health/")
        assert r.status_code == 200
        for key in ("workflows", "workflow_latency_ms", "activity", "records",
                    "errors", "storage", "generated_at"):
            assert key in r.data

    def test_no_ai_metric(self, ws):
        c, _, _ = _client(ws, "admin")
        r = c.get(f"{BASE}/health/")
        assert r.data["ai"] is None                 # hard constraint: no AI, by design
        assert r.data["api_latency_ms"] is None     # not collected → null, not faked

    def test_requires_admin(self, ws):
        c, _, _ = _client(ws, "viewer", email="v@acme.com")
        assert c.get(f"{BASE}/health/").status_code == 403

    def test_reflects_workspace_activity(self, ws):
        c, user, member = _client(ws, "admin")
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                        name="Name", field_type="text", is_promoted=True)
        ent.refresh_from_db()
        for n in ("A", "B"):
            RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                        data={"name": n})
        r = c.get(f"{BASE}/health/")
        assert r.data["records"]["created_total"] >= 2
        assert r.data["activity"]["dau"] >= 1       # the creating user counts as active
        assert r.data["storage"]["entity_count"] >= 1

    def test_workspace_isolation(self, ws):
        # activity in another workspace must not show up here
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc, ouser, omember = _client(other, "admin", email="o@other.com")
        ent = SchemaRegistryService.create_entity(
            workspace_id=other.id, slug="lead", name="Lead", plural_name="Leads")
        SchemaRegistryService.add_field(workspace_id=other.id, entity_slug="lead", slug="name",
                                        name="Name", field_type="text", is_promoted=True)
        ent.refresh_from_db()
        RecordService.create_record(workspace_id=other.id, member=omember, entity=ent,
                                    data={"name": "X"})
        c, _, _ = _client(ws, "admin")
        r = c.get(f"{BASE}/health/")
        assert r.data["records"]["created_total"] == 0   # ws has no records
