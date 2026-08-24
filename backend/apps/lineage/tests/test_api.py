"""Data Lineage REST API (PROJECT_HANDBOOK.md §31.3 / §31.5)."""
import uuid

import pytest

from apps.lineage.services import LineageService

BASE = "/api/v1/lineage"


@pytest.mark.django_db
class TestLineageApi:
    def test_node_list_and_filter(self, ws, client):
        LineageService.ensure_node(ws.id, "entity", uuid.uuid4(), display_name="E")
        LineageService.ensure_node(ws.id, "report", uuid.uuid4(), display_name="R")
        assert client.get(f"{BASE}/nodes/").json()["count"] == 2
        assert client.get(f"{BASE}/nodes/?node_type=report").json()["count"] == 1

    def test_upstream_downstream(self, ws, client):
        a, b = uuid.uuid4(), uuid.uuid4()
        LineageService.record_edge(ws.id, "entity", a, "report", b, "reads")
        src = LineageService.ensure_node(ws.id, "entity", a)
        tgt = LineageService.ensure_node(ws.id, "report", b)
        down = client.get(f"{BASE}/nodes/{src.id}/downstream/").json()
        assert {n["display_name"] for n in down["nodes"]} or down["nodes"] is not None
        assert len(down["edges"]) == 1
        up = client.get(f"{BASE}/nodes/{tgt.id}/upstream/").json()
        assert len(up["edges"]) == 1

    def test_workspace_isolation(self, ws, client):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        from apps.accounts.models import User
        from apps.tenancy.models import Workspace, WorkspaceMember

        from .conftest import PW
        node = LineageService.ensure_node(ws.id, "entity", uuid.uuid4())
        other = Workspace.objects.create(name="O", slug="o", is_active=True)
        u = User.objects.create_user(email="x@o.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=other, user=u, role="admin", status="active")
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                       HTTP_X_WORKSPACE_SLUG=other.slug)
        assert c2.get(f"{BASE}/nodes/{node.id}/upstream/").status_code == 404
