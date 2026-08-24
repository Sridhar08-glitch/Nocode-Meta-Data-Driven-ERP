"""Solution Package Platform REST API (/api/v1/packages/)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.solution_templates.models import InstalledSolution, SolutionTemplate
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/packages"


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


@pytest.mark.django_db
def test_core_endpoint(workspace):
    c, _ = _client(workspace, "member")
    resp = c.get(f"{BASE}/core/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["core_version"]
    assert body["engines"]["accounting"]["available"] is True


@pytest.mark.django_db
def test_catalog_and_matrix(workspace):
    SolutionTemplate.objects.create(
        slug="pos", name="POS", version="1.0.0", is_published=True,
        manifest={"schema_version": 1, "package": {
            "slug": "pos", "version": "1.0.0",
            "requires_packages": [{"slug": "inventory", "version": ">=1.0.0"}]}})
    c, _ = _client(workspace, "member")
    assert any(r["slug"] == "pos" for r in c.get(f"{BASE}/").json())
    matrix = c.get(f"{BASE}/dependency-matrix/").json()
    row = next(r for r in matrix["packages"] if r["slug"] == "pos")
    assert row["requires_packages"][0]["slug"] == "inventory"


@pytest.mark.django_db
def test_preflight_endpoint_blocks_missing_dependency(workspace):
    c, _ = _client(workspace, "member")
    resp = c.post(f"{BASE}/preflight/", {"manifest": {
        "schema_version": 1, "package": {
            "slug": "pos", "version": "1.0.0",
            "requires_packages": [{"slug": "inventory", "version": ">=1.0.0"}]}}},
        format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert any("inventory" in e for e in body["errors"])


@pytest.mark.django_db
def test_preflight_template_passes(workspace):
    tpl = SolutionTemplate.objects.create(
        slug="simple", name="Simple", version="1.0.0", is_published=True,
        manifest={"schema_version": 1, "entities": [{"slug": "thing", "fields": []}]})
    c, _ = _client(workspace, "member")
    resp = c.post(f"{BASE}/preflight/", {"template_id": str(tpl.id)}, format="json")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.django_db
def test_installed_and_lifecycle_admin_gated(workspace):
    tpl = SolutionTemplate.objects.create(
        slug="widget", name="Widget", version="1.0.0", is_published=True,
        manifest={"schema_version": 1,
                  "package": {"slug": "widget", "version": "1.0.0"},
                  "entities": [{"slug": "widget", "name": "Widget",
                                "plural_name": "Widgets", "fields": [
                                    {"slug": "name", "name": "Name", "field_type": "text",
                                     "is_promoted": True}]}]})
    # install via the solution-templates API path
    ca, _ = _client(workspace, "admin")
    inst = InstalledSolution.objects.create(
        workspace_id=workspace.id, solution_slug="widget", solution_name="Widget",
        installed_version="1.0.0", status="active", installed_manifest=tpl.manifest)

    # member can read installed registry
    cm, _ = _client(workspace, "member", "m@e.com")
    rows = cm.get(f"{BASE}/installed/").json()
    assert rows[0]["slug"] == "widget"

    # member cannot disable
    assert cm.post(f"{BASE}/installed/{inst.id}/disable/").status_code == 403
    # admin can disable then enable
    assert ca.post(f"{BASE}/installed/{inst.id}/disable/").status_code == 200
    assert InstalledSolution.objects.get(id=inst.id).status == "disabled"
    assert ca.post(f"{BASE}/installed/{inst.id}/enable/").status_code == 200
    assert InstalledSolution.objects.get(id=inst.id).status == "active"


@pytest.mark.django_db
def test_upgrade_via_api(workspace):
    tpl = SolutionTemplate.objects.create(
        slug="widget", name="Widget", version="1.1.0", is_published=True,
        manifest={"schema_version": 1,
                  "package": {"slug": "widget", "version": "1.1.0"},
                  "entities": [{"slug": "widget", "name": "Widget", "plural_name": "Widgets",
                                "fields": [{"slug": "name", "name": "Name",
                                            "field_type": "text", "is_promoted": True},
                                           {"slug": "color", "name": "Color",
                                            "field_type": "text", "is_promoted": True}]}]})
    inst = InstalledSolution.objects.create(
        workspace_id=workspace.id, solution_slug="widget", solution_name="Widget",
        installed_version="1.0.0", status="active",
        installed_manifest={"schema_version": 1, "package": {"slug": "widget",
                                                             "version": "1.0.0"}})
    ca, _ = _client(workspace, "admin")
    resp = ca.post(f"{BASE}/installed/{inst.id}/upgrade/",
                   {"template_id": str(tpl.id)}, format="json")
    assert resp.status_code == 200
    assert InstalledSolution.objects.get(id=inst.id).installed_version == "1.1.0"
