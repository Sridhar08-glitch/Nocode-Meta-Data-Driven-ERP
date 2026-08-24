"""
Config VCS branch + 3-way merge (Phase 1.28).

Service-level tests for the merge algorithm (clean / conflict / resolve) and HTTP tests
for the /api/v1/config-vcs/ branch + merge-request endpoints.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.config_vcs import services as cvcs
from apps.metadata.models import EntityDefinition
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/config-vcs"


# ── service-level fixtures ────────────────────────────────────────────────────
@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=w, slug="lead", name="Lead", plural_name="Leads")
    return w


def _rename(ws, name):
    SchemaRegistryService.update_entity(workspace_id=ws, slug="lead", updates={"name": name})


@pytest.mark.django_db
class TestBranchMergeService:
    def test_create_branch_from_main(self, ws):
        cvcs.commit(workspace_id=ws, message="init")
        b = cvcs.create_branch(workspace_id=ws, name="draft")
        main = cvcs.get_branch(ws, "main")
        assert b.head_sha == main.head_sha
        assert b.base_sha == main.head_sha

    def test_duplicate_branch_rejected(self, ws):
        cvcs.commit(workspace_id=ws, message="init")
        cvcs.create_branch(workspace_id=ws, name="draft")
        with pytest.raises(cvcs.ConfigVCSError):
            cvcs.create_branch(workspace_id=ws, name="draft")

    def test_clean_merge_takes_source_change(self, ws):
        cvcs.commit(workspace_id=ws, message="base")          # main @ base (Lead)
        cvcs.create_branch(workspace_id=ws, name="draft")
        _rename(ws, "Prospect")
        cvcs.commit(workspace_id=ws, message="draft change", branch="draft")  # draft diverges
        mr = cvcs.open_merge_request(workspace_id=ws, source_branch="draft",
                                     target_branch="main", title="t", opened_by=uuid.uuid4())
        merged_mr, conflicts = cvcs.merge(workspace_id=ws, mr_id=mr.id)
        assert conflicts == []
        assert merged_mr.status == "merged"
        main = cvcs.get_branch(ws, "main")
        assert main.head_sha == merged_mr.merge_commit_sha
        head_commit = cvcs.get_commit(ws, main.head_sha)
        lead = next(e for e in head_commit.payload["entities"] if e["slug"] == "lead")
        assert lead["name"] == "Prospect"

    def test_conflict_detected_then_resolved(self, ws):
        cvcs.commit(workspace_id=ws, message="base")          # base: Lead
        cvcs.create_branch(workspace_id=ws, name="draft")
        _rename(ws, "FromDraft")
        cvcs.commit(workspace_id=ws, message="draft", branch="draft")
        _rename(ws, "FromMain")
        cvcs.commit(workspace_id=ws, message="main", branch="main")
        mr = cvcs.open_merge_request(workspace_id=ws, source_branch="draft",
                                     target_branch="main", title="t", opened_by=uuid.uuid4())
        merged_mr, conflicts = cvcs.merge(workspace_id=ws, mr_id=mr.id)
        assert len(conflicts) == 1
        assert merged_mr.status == "conflict"
        key = conflicts[0]["key"]
        assert key.startswith("entities:")

        # resolve in favour of the draft (source)
        resolved, conflicts2 = cvcs.resolve_merge_request(
            workspace_id=ws, mr_id=mr.id, resolutions={key: "source"})
        assert conflicts2 == []
        assert resolved.status == "merged"
        head_commit = cvcs.get_commit(ws, cvcs.get_branch(ws, "main").head_sha)
        lead = next(e for e in head_commit.payload["entities"] if e["slug"] == "lead")
        assert lead["name"] == "FromDraft"

    def test_merge_base_finds_common_ancestor(self, ws):
        c1 = cvcs.commit(workspace_id=ws, message="base")
        cvcs.create_branch(workspace_id=ws, name="draft")
        _rename(ws, "X")
        cd = cvcs.commit(workspace_id=ws, message="d", branch="draft")
        _rename(ws, "Y")
        cm = cvcs.commit(workspace_id=ws, message="m", branch="main")
        assert cvcs._merge_base(ws, cd.sha, cm.sha) == c1.sha

    def test_merge_same_branch_rejected(self, ws):
        cvcs.commit(workspace_id=ws, message="base")
        with pytest.raises(cvcs.ConfigVCSError):
            cvcs.open_merge_request(workspace_id=ws, source_branch="main",
                                    target_branch="main", title="t", opened_by=uuid.uuid4())

    def test_double_merge_rejected(self, ws):
        cvcs.commit(workspace_id=ws, message="base")
        cvcs.create_branch(workspace_id=ws, name="draft")
        _rename(ws, "Z")
        cvcs.commit(workspace_id=ws, message="d", branch="draft")
        mr = cvcs.open_merge_request(workspace_id=ws, source_branch="draft",
                                     target_branch="main", title="t", opened_by=uuid.uuid4())
        cvcs.merge(workspace_id=ws, mr_id=mr.id)
        with pytest.raises(cvcs.ConfigVCSError):
            cvcs.merge(workspace_id=ws, mr_id=mr.id)


# ── HTTP-level ────────────────────────────────────────────────────────────────
@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def admin_client(workspace):
    user = User.objects.create_user(email="admin@example.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="admin", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


@pytest.fixture
def member_client(workspace):
    user = User.objects.create_user(email="member@example.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="member", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


def _seed(workspace):
    SchemaRegistryService.create_entity(workspace_id=workspace.id, slug="lead",
                                        name="Lead", plural_name="Leads")


@pytest.mark.django_db
class TestBranchMergeAPI:
    def test_create_and_list_branches(self, admin_client, workspace):
        _seed(workspace)
        admin_client.post(f"{BASE}/commit/", {"message": "init"}, format="json")
        cr = admin_client.post(f"{BASE}/branches/", {"name": "draft"}, format="json")
        assert cr.status_code == 201
        assert cr.data["name"] == "draft"
        lr = admin_client.get(f"{BASE}/branches/")
        assert lr.status_code == 200
        names = {b["name"] for b in lr.data["results"]}
        assert {"main", "draft"} <= names

    def test_member_forbidden(self, member_client, workspace):
        r = member_client.get(f"{BASE}/branches/")
        assert r.status_code == 403

    def test_full_merge_flow_via_api(self, admin_client, workspace):
        _seed(workspace)
        admin_client.post(f"{BASE}/commit/", {"message": "base"}, format="json")
        admin_client.post(f"{BASE}/branches/", {"name": "draft"}, format="json")
        # diverge draft
        SchemaRegistryService.update_entity(workspace_id=workspace.id, slug="lead",
                                            updates={"name": "Prospect"})
        admin_client.post(f"{BASE}/commit/", {"message": "draft", "branch": "draft"}, format="json")
        mr = admin_client.post(f"{BASE}/merge-requests/",
                               {"source_branch": "draft", "target_branch": "main",
                                "title": "Publish draft"}, format="json")
        assert mr.status_code == 201
        mr_id = mr.data["id"]
        merge = admin_client.post(f"{BASE}/merge-requests/{mr_id}/merge/", {}, format="json")
        assert merge.status_code == 200
        assert merge.data["status"] == "merged"

    def test_conflict_returns_409_then_resolve(self, admin_client, workspace):
        _seed(workspace)
        admin_client.post(f"{BASE}/commit/", {"message": "base"}, format="json")
        admin_client.post(f"{BASE}/branches/", {"name": "draft"}, format="json")
        SchemaRegistryService.update_entity(workspace_id=workspace.id, slug="lead",
                                            updates={"name": "FromDraft"})
        admin_client.post(f"{BASE}/commit/", {"message": "d", "branch": "draft"}, format="json")
        SchemaRegistryService.update_entity(workspace_id=workspace.id, slug="lead",
                                            updates={"name": "FromMain"})
        admin_client.post(f"{BASE}/commit/", {"message": "m", "branch": "main"}, format="json")
        mr_id = admin_client.post(f"{BASE}/merge-requests/",
                                  {"source_branch": "draft", "target_branch": "main",
                                   "title": "t"}, format="json").data["id"]
        merge = admin_client.post(f"{BASE}/merge-requests/{mr_id}/merge/", {}, format="json")
        assert merge.status_code == 409
        assert len(merge.data["conflicts"]) == 1
        key = merge.data["conflicts"][0]["key"]

        resolve = admin_client.post(f"{BASE}/merge-requests/{mr_id}/resolve/",
                                    {"resolutions": {key: "target"}}, format="json")
        assert resolve.status_code == 200
        assert resolve.data["status"] == "merged"
        assert EntityDefinition.objects.get(workspace_id=workspace.id, slug="lead").name == "FromMain"

    def test_workspace_isolation_on_merge_request_detail(self, admin_client, workspace):
        _seed(workspace)
        admin_client.post(f"{BASE}/commit/", {"message": "base"}, format="json")
        admin_client.post(f"{BASE}/branches/", {"name": "draft"}, format="json")
        mr_id = admin_client.post(f"{BASE}/merge-requests/",
                                  {"source_branch": "draft", "target_branch": "main",
                                   "title": "t"}, format="json").data["id"]
        # another workspace cannot see it
        other_ws = Workspace.objects.create(name="Other", slug="other", is_active=True)
        ou = User.objects.create_user(email="o@example.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=other_ws, user=ou, role="admin", status="active")
        oc = APIClient()
        oc.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(ou)}",
                       HTTP_X_WORKSPACE_SLUG=other_ws.slug)
        r = oc.get(f"{BASE}/merge-requests/{mr_id}/")
        assert r.status_code == 404
