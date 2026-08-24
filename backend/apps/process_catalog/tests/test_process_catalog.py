"""Business Process Catalog (Phase 1.34) — browse, preview, install (wires a workflow)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import EntityDefinition
from apps.process_catalog.models import ProcessBlueprint
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import WorkflowDefinition

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/process-catalog"

MANIFEST = {
    "schema_version": 1,
    "entities": [{
        "slug": "support_ticket", "name": "Support Ticket", "has_physical_table": True,
        "fields": [{"slug": "subject", "name": "Subject", "field_type": "text", "is_promoted": True}],
    }],
    "workflows": [{
        "slug": "ticket_ack", "name": "Ticket Ack", "trigger_type": "record_created",
        "entity_slug": "support_ticket",
        "steps": [{"slug": "s1", "step_type": "action_send_notification",
                   "name": "Notify", "is_entry": True, "config": {}}],
        "edges": [],
    }],
}


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(ws, role="admin", email=None, is_staff=False):
    email = email or f"{role}@acme.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True, is_staff=is_staff)
    WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


def _blueprint(published=True, slug="helpdesk"):
    return ProcessBlueprint.objects.create(
        name="Helpdesk", slug=slug, category="support", manifest=MANIFEST,
        is_published=published)


@pytest.mark.django_db
class TestProcessCatalog:
    def test_browse_lists_published_only(self, ws):
        _blueprint(published=True, slug="published")
        _blueprint(published=False, slug="draft")
        c = _client(ws, "member")
        r = c.get(f"{BASE}/")
        slugs = {b["slug"] for b in r.data["results"]}
        assert "published" in slugs and "draft" not in slugs

    def test_preview_validates_manifest(self, ws):
        bp = _blueprint()
        c = _client(ws, "member")
        r = c.get(f"{BASE}/{bp.id}/")
        assert r.status_code == 200
        assert r.data["valid"] is True
        assert r.data["summary"]["entities"] == 1
        assert r.data["summary"]["workflows"] == 1

    def test_install_creates_entity_and_workflow(self, ws):
        bp = _blueprint()
        c = _client(ws, "admin")
        r = c.post(f"{BASE}/{bp.id}/install/")
        assert r.status_code == 201
        assert EntityDefinition.objects.filter(
            workspace_id=ws.id, slug="support_ticket").exists()
        wf = WorkflowDefinition.objects.filter(workspace_id=ws.id, slug="ticket_ack").first()
        assert wf is not None and wf.status == "active"
        bp.refresh_from_db()
        assert bp.install_count == 1

    def test_member_cannot_install(self, ws):
        bp = _blueprint()
        c = _client(ws, "member")
        assert c.post(f"{BASE}/{bp.id}/install/").status_code == 403

    def test_cannot_install_unpublished(self, ws):
        bp = _blueprint(published=False)
        c = _client(ws, "admin")
        # non-staff can't even see an unpublished blueprint
        assert c.get(f"{BASE}/{bp.id}/").status_code == 404

    def test_staff_can_create_and_publish(self, ws):
        staff = _client(ws, "admin", email="staff@acme.com", is_staff=True)
        cr = staff.post(f"{BASE}/", {"name": "New", "slug": "new", "manifest": MANIFEST},
                        format="json")
        assert cr.status_code == 201
        bp_id = cr.data["id"]
        assert ProcessBlueprint.objects.get(id=bp_id).is_published is False
        pub = staff.post(f"{BASE}/{bp_id}/publish/")
        assert pub.status_code == 200 and pub.data["is_published"] is True

    def test_non_staff_cannot_create(self, ws):
        c = _client(ws, "admin")   # admin but not is_staff
        assert c.post(f"{BASE}/", {"name": "X", "slug": "x", "manifest": MANIFEST},
                      format="json").status_code == 403
