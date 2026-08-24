"""Phase 1.10 — audit trail API (a projection of the event store)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.projections.services import run_projections
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _client(ws, email, role):
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return user, c


@pytest.fixture
def workspace(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True, is_required=True)
    ent.refresh_from_db()
    return ws


@pytest.mark.django_db
class TestAuditAPI:
    def test_audit_list_after_projection(self, workspace):
        admin_user, ac = _client(workspace, "admin@acme.com", "admin")
        ac.post("/api/v1/data/lead/", {"name": "A"}, format="json")
        run_projections()                              # drain events → AuditLog
        r = ac.get("/api/v1/audit/")
        assert r.status_code == 200
        actions = {e["action"] for e in r.data["results"]}
        assert {"entity.created", "record.created"} <= actions

    def test_audit_filter_by_resource(self, workspace):
        admin_user, ac = _client(workspace, "admin2@acme.com", "admin")
        ac.post("/api/v1/data/lead/", {"name": "A"}, format="json")
        run_projections()
        r = ac.get("/api/v1/audit/", {"resource_type": "record"})
        assert r.status_code == 200
        assert all(e["resource_type"] == "record" for e in r.data["results"])
        assert r.data["count"] >= 1

    def test_audit_requires_admin(self, workspace):
        _, vc = _client(workspace, "viewer@acme.com", "viewer")
        assert vc.get("/api/v1/audit/").status_code == 403
