"""Workflow REST API (PROJECT_HANDBOOK.md §21.7)."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/workflows"


def _client(workspace, email, role="admin"):
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role,
                                   status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return user, c


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def admin(workspace):
    return _client(workspace, "admin@acme.com", role="admin")


@pytest.mark.django_db
class TestDefinitionApi:
    def test_create_list_get_patch(self, admin):
        _, c = admin
        r = c.post(f"{BASE}/definitions/",
                   {"name": "Lead Flow", "slug": "lead-flow", "trigger_type": "manual"},
                   format="json")
        assert r.status_code == 201, r.content
        wid = r.json()["id"]
        assert c.get(f"{BASE}/definitions/").json()["count"] == 1
        assert c.get(f"{BASE}/definitions/{wid}/").json()["slug"] == "lead-flow"
        r = c.patch(f"{BASE}/definitions/{wid}/", {"description": "hi"}, format="json")
        assert r.json()["description"] == "hi"

    def test_activate_pause(self, admin):
        _, c = admin
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "F", "slug": "f", "trigger_type": "manual"},
                     format="json").json()["id"]
        assert c.post(f"{BASE}/definitions/{wid}/activate/").json()["status"] == "active"
        assert c.post(f"{BASE}/definitions/{wid}/pause/").json()["status"] == "paused"

    def test_steps_and_edges(self, admin):
        _, c = admin
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "F", "slug": "f", "trigger_type": "manual"},
                     format="json").json()["id"]
        s1 = c.post(f"{BASE}/definitions/{wid}/steps/",
                    {"step_type": "transform", "name": "s1", "is_entry": True,
                     "config": {"mappings": {}}}, format="json").json()
        s2 = c.post(f"{BASE}/definitions/{wid}/steps/",
                    {"step_type": "transform", "name": "s2"}, format="json").json()
        assert c.get(f"{BASE}/definitions/{wid}/steps/").json()["count"] == 2
        e = c.post(f"{BASE}/definitions/{wid}/edges/",
                   {"source_step_id": s1["id"], "target_step_id": s2["id"]},
                   format="json")
        assert e.status_code == 201
        assert c.get(f"{BASE}/definitions/{wid}/edges/").json()["count"] == 1
        eid = e.json()["id"]
        assert c.delete(f"{BASE}/definitions/{wid}/edges/{eid}/").status_code == 204

    def test_duplicate(self, admin):
        _, c = admin
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "F", "slug": "f", "trigger_type": "manual"},
                     format="json").json()["id"]
        c.post(f"{BASE}/definitions/{wid}/steps/",
               {"step_type": "transform", "name": "s1", "is_entry": True}, format="json")
        r = c.post(f"{BASE}/definitions/{wid}/duplicate/", {"slug": "f-copy"}, format="json")
        assert r.status_code == 201
        new_id = r.json()["id"]
        assert c.get(f"{BASE}/definitions/{new_id}/steps/").json()["count"] == 1


@pytest.mark.django_db
class TestTriggerAndRunsApi:
    def _webhook_wf(self, c):
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "Hook", "slug": "hook", "trigger_type": "webhook"},
                     format="json").json()["id"]
        c.post(f"{BASE}/definitions/{wid}/steps/",
               {"step_type": "transform", "name": "t", "is_entry": True,
                "config": {"mappings": {"flag": "1"}}}, format="json")
        c.post(f"{BASE}/definitions/{wid}/activate/")
        return wid

    def test_webhook_trigger_runs_workflow(self, admin):
        _, c = admin
        wid = self._webhook_wf(c)
        r = c.post(f"{BASE}/definitions/{wid}/trigger/", {"hello": "world"}, format="json")
        assert r.status_code == 202, r.content
        run_id = r.json()["id"]
        detail = c.get(f"{BASE}/runs/{run_id}/").json()
        assert detail["status"] == "completed"
        assert len(detail["step_runs"]) == 1
        assert c.get(f"{BASE}/runs/").json()["count"] >= 1

    def test_trigger_rejects_non_webhook(self, admin):
        _, c = admin
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "M", "slug": "m", "trigger_type": "manual",
                      "status": "active"}, format="json").json()["id"]
        c.post(f"{BASE}/definitions/{wid}/activate/")
        r = c.post(f"{BASE}/definitions/{wid}/trigger/", {}, format="json")
        assert r.status_code == 400

    def test_retry_run(self, admin):
        _, c = admin
        wid = self._webhook_wf(c)
        run_id = c.post(f"{BASE}/definitions/{wid}/trigger/", {}, format="json").json()["id"]
        r = c.post(f"{BASE}/runs/{run_id}/retry/")
        assert r.status_code == 201
        assert r.json()["id"] != run_id


@pytest.mark.django_db
class TestApiAuthz:
    def test_viewer_cannot_create(self, workspace):
        _, c = _client(workspace, "viewer@acme.com", role="viewer")
        r = c.post(f"{BASE}/definitions/",
                   {"name": "F", "slug": "f", "trigger_type": "manual"}, format="json")
        assert r.status_code == 403

    def test_viewer_can_list(self, workspace):
        _, c = _client(workspace, "viewer@acme.com", role="viewer")
        assert c.get(f"{BASE}/definitions/").status_code == 200

    def test_other_workspace_cannot_see(self, admin):
        _, c = admin
        wid = c.post(f"{BASE}/definitions/",
                     {"name": "F", "slug": "f", "trigger_type": "manual"},
                     format="json").json()["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        _, c2 = _client(other, "x@other.com", role="admin")
        assert c2.get(f"{BASE}/definitions/{wid}/").status_code == 404
