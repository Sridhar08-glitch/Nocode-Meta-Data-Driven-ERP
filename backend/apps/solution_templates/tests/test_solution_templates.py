"""
Solution Template Framework (Phase P2.4A) — manifest validation, full-stack install via
reused engines, idempotency, soft-uninstall (data preserved), the standard library, and
the REST API (browse/preview/install gating + workspace isolation).
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import EntityDefinition, FormDefinition, ViewDefinition
from apps.permissions.models import Permission, Role
from apps.reporting.models import Dashboard, Report
from apps.solution_templates import services
from apps.solution_templates.models import InstalledSolution, SolutionTemplate
from apps.solution_templates.seeding import seed_system_templates
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application, HomeLayout, Navigation
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import WorkflowDefinition

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/solution-templates"


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


def _seed():
    return seed_system_templates()[0]


# ── validation ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_validate_catches_bad_sections():
    errors = validate_solution_manifest({
        "schema_version": 1,
        "views": [{"slug": "v1", "view_type": "nope"}],          # bad view_type + no entity_slug
        "forms": [{"slug": "f1"}],                                # missing entity_slug
        "roles": [{"slug": "Bad Slug"}],                          # invalid slug
    })
    joined = " ".join(errors)
    assert "view_type" in joined
    assert "requires entity_slug" in joined
    assert "not a valid slug" in joined


@pytest.mark.django_db
def test_seed_is_idempotent():
    a = seed_system_templates()
    b = seed_system_templates()
    assert SolutionTemplate.objects.filter(slug="sales_crm").count() == 1
    assert a[0].slug == b[0].slug == "sales_crm"


@pytest.mark.django_db
def test_seeded_manifest_is_valid():
    tpl = _seed()
    assert validate_solution_manifest(tpl.manifest) == []


# ── install (service layer) ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_install_provisions_full_stack():
    tpl = _seed()
    ws = uuid.uuid4()
    installed = services.install(template_id=tpl.id, workspace_id=ws, installed_by=None)

    assert EntityDefinition.objects.filter(workspace_id=ws, slug="customer").exists()
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="sales_order").exists()
    assert FormDefinition.objects.filter(workspace_id=ws).count() == 3
    assert ViewDefinition.objects.filter(workspace_id=ws).count() == 2
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="so_approval").exists()
    assert Report.objects.filter(workspace_id=ws).count() == 5
    assert Role.objects.filter(workspace_id=ws, slug="administrator").exists()
    assert Permission.objects.filter(workspace_id=ws).exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 3
    assert Application.objects.filter(workspace_id=ws, slug="sales_crm").exists()
    assert Navigation.objects.filter(workspace_id=ws).exists()
    assert HomeLayout.objects.filter(workspace_id=ws).exists()

    # InstalledSolution records what was provisioned.
    assert len(installed.created_entity_ids) == 3
    assert installed.summary["dashboards"] == 3

    # The app-scoped navigation/home are pointed at the created application.
    app = Application.objects.get(workspace_id=ws, slug="sales_crm")
    assert Navigation.objects.filter(workspace_id=ws, target_id=app.id).exists()
    assert app.included_entity_ids  # entity slugs resolved to ids


@pytest.mark.django_db
def test_install_is_idempotent_on_overlap():
    tpl = _seed()
    ws = uuid.uuid4()
    services.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    # Re-install: existing entities/fields/forms/app are skipped, not duplicated, no crash.
    services.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="customer").count() == 1
    assert Application.objects.filter(workspace_id=ws, slug="sales_crm").count() == 1
    assert InstalledSolution.objects.filter(workspace_id=ws).count() == 2


@pytest.mark.django_db
def test_uninstall_soft_preserves_data():
    tpl = _seed()
    ws = uuid.uuid4()
    installed = services.install(template_id=tpl.id, workspace_id=ws, installed_by=None)

    obj = services.uninstall(installed_id=installed.id, workspace_id=ws, actor_id=None)
    assert obj.status == "disabled"
    # Workflows archived, applications unpublished — but entities/records preserved.
    assert WorkflowDefinition.objects.get(workspace_id=ws, slug="so_approval").status == "archived"
    assert Application.objects.get(workspace_id=ws, slug="sales_crm").is_published is False
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="customer").exists()


@pytest.mark.django_db
def test_unpublished_template_cannot_install():
    tpl = _seed()
    tpl.is_published = False
    tpl.save(update_fields=["is_published"])
    with pytest.raises(services.SolutionTemplateError):
        services.install(template_id=tpl.id, workspace_id=uuid.uuid4(), installed_by=None)


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_browse_returns_published_only(workspace):
    _seed()
    SolutionTemplate.objects.create(slug="draft_one", name="Draft", is_published=False)
    c, _ = _client(workspace, "member")
    resp = c.get(f"{BASE}/")
    assert resp.status_code == 200
    slugs = {row["slug"] for row in resp.json()}
    assert "sales_crm" in slugs
    assert "draft_one" not in slugs


@pytest.mark.django_db
def test_library_endpoint_returns_standard_objects(workspace):
    c, _ = _client(workspace, "member")
    resp = c.get(f"{BASE}/library/")
    assert resp.status_code == 200
    body = resp.json()
    obj_slugs = {o["slug"] for o in body["business_objects"]}
    assert {"customer", "vendor", "purchase_order", "sales_order"} <= obj_slugs
    assert len(body["roles"]) == 5


@pytest.mark.django_db
def test_member_cannot_install_admin_can(workspace):
    tpl = _seed()
    cm, _ = _client(workspace, "member", "m@e.com")
    assert cm.post(f"{BASE}/{tpl.id}/install/").status_code == 403

    ca, _ = _client(workspace, "admin", "a@e.com")
    resp = ca.post(f"{BASE}/{tpl.id}/install/")
    assert resp.status_code == 201
    assert EntityDefinition.objects.filter(
        workspace_id=workspace.id, slug="customer").exists()
    assert resp.json()["solution_slug"] == "sales_crm"


@pytest.mark.django_db
def test_preview_reports_summary_and_validity(workspace):
    tpl = _seed()
    c, _ = _client(workspace, "member")
    resp = c.get(f"{BASE}/{tpl.id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["summary"]["entities"] == 3
    assert body["summary"]["dashboards"] == 3


@pytest.mark.django_db
def test_cross_workspace_template_is_global_but_install_is_scoped(workspace):
    """Templates are a global catalog; preview works for any member, install lands only in
    the caller's workspace."""
    tpl = _seed()
    other = Workspace.objects.create(name="Other", slug="other", is_active=True)
    ca, _ = _client(workspace, "admin")
    ca.post(f"{BASE}/{tpl.id}/install/")
    assert EntityDefinition.objects.filter(workspace_id=workspace.id, slug="customer").exists()
    assert not EntityDefinition.objects.filter(workspace_id=other.id, slug="customer").exists()


@pytest.mark.django_db
def test_staff_can_create_template(workspace):
    c, user = _client(workspace, "admin")
    # non-staff blocked
    assert c.post(f"{BASE}/", {"name": "X", "slug": "x_sol", "manifest": {"schema_version": 1}},
                  format="json").status_code == 403
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    resp = c.post(f"{BASE}/", {"name": "X", "slug": "x_sol",
                               "manifest": {"schema_version": 1}}, format="json")
    assert resp.status_code == 201
    assert SolutionTemplate.objects.filter(slug="x_sol").exists()
