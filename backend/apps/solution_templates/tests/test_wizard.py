"""
Create Solution Wizard (Phase P2.4B) — manifest composition, dependency resolution, preview
warnings, provisioning through the SHARED installer, audit events, and API gating.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.eventstore.models import DomainEvent
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.reporting.models import Dashboard
from apps.solution_templates import wizard
from apps.solution_templates.models import InstalledSolution
from apps.studio.models import Application
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import WorkflowDefinition

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/solution-templates/wizard"


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


def _crm_selection():
    return {
        "solution_type": "crm",
        "business_objects": ["customer", "contact", "sales_order"],
        "workflows": ["approval", "assignment"],
        "roles": ["administrator", "manager", "user"],
        "dashboards": ["executive", "operational"],
        "reports": ["summary", "detail", "trend"],
        "config": {"solution_name": "Sales CRM", "application_name": "Sales CRM",
                   "icon": "Users", "color": "#2563eb"},
    }


# ── composition + dependencies ───────────────────────────────────────────────
def test_resolve_pulls_lookup_dependencies():
    # contact → customer; appointment → patient + practitioner
    assert "customer" in wizard.resolve_dependencies(["contact"])
    resolved = wizard.resolve_dependencies(["appointment"])
    assert {"appointment", "patient", "practitioner"} <= set(resolved)


def test_build_manifest_composes_full_stack():
    m = wizard.build_manifest(_crm_selection())
    assert m["schema_version"] == 1
    slugs = {e["slug"] for e in m["entities"]}
    assert {"customer", "contact", "sales_order"} <= slugs
    assert len(m["forms"]) == len(m["entities"])
    assert len(m["views"]) == len(m["entities"])
    # workflows bound to the primary entity, prefixed slug, no collision
    assert all(w["entity_slug"] == "customer" for w in m["workflows"])
    assert {w["slug"] for w in m["workflows"]} == {"sales_crm_approval", "sales_crm_assignment"}
    # only the 3 requested reports
    assert {r["slug"] for r in m["reports"]} == {"summary_report", "detail_report", "trend_report"}
    # approval workflow ⇒ approval notification template auto-added
    assert any(t["slug"] == "approval_requested" for t in m["notification_templates"])
    app = m["applications"][0]
    assert app["slug"] == "sales_crm"
    assert app["role_slugs"] == ["administrator", "manager", "user"]


def test_build_manifest_accepts_keys_or_slugs():
    # Dashboard library key is 'executive' but its slug is 'executive_dashboard' — both resolve.
    sel = {"business_objects": ["customer"], "workflows": [], "roles": ["administrator"],
           "dashboards": ["executive_dashboard"], "reports": ["summary_report"],
           "config": {"solution_name": "X"}}
    m = wizard.build_manifest(sel)
    assert {d["slug"] for d in m["dashboards"]} == {"executive_dashboard"}
    assert {r["slug"] for r in m["reports"]} == {"summary_report"}


@pytest.mark.django_db
def test_build_manifest_validates_clean():
    from apps.solution_templates.validators import validate_solution_manifest
    assert validate_solution_manifest(wizard.build_manifest(_crm_selection())) == []


# ── preview ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_preview_reports_dependencies_and_collisions():
    ws = uuid.uuid4()
    # Pre-existing customer entity → collision warning + extend note.
    EntityDefinition.objects.create(workspace_id=ws, slug="customer", name="Customer",
                                    plural_name="Customers")
    sel = {"business_objects": ["contact"],  # contact depends on customer
           "config": {"solution_name": "Mini"}}
    result = wizard.preview(sel, workspace_id=ws, actor_id=None)
    assert "customer" in result["resolved_objects"]
    assert any("Auto-included dependencies" in w for w in result["warnings"])
    assert any("already exists" in w for w in result["warnings"])
    # previewed audit event emitted
    assert DomainEvent.objects.filter(
        aggregate_type="solution_wizard", event_type="solution.wizard.previewed").exists()


# ── create (provisions via shared installer) ─────────────────────────────────
@pytest.mark.django_db
def test_create_provisions_full_stack_and_audits():
    ws = uuid.uuid4()
    installed = wizard.create(_crm_selection(), workspace_id=ws, actor_id=None)

    assert isinstance(installed, InstalledSolution)
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="customer").exists()
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="sales_crm_approval").exists()
    assert Role.objects.filter(workspace_id=ws, slug="administrator").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 2
    assert Application.objects.filter(workspace_id=ws, slug="sales_crm").exists()
    # both wizard.created and the installer's solution_template.installed fired
    assert DomainEvent.objects.filter(
        aggregate_type="solution_wizard", event_type="solution.wizard.created").exists()
    assert DomainEvent.objects.filter(event_type="solution_template.installed").exists()


@pytest.mark.django_db
def test_create_emits_failed_on_install_error(monkeypatch):
    from apps.solution_templates import services
    ws = uuid.uuid4()

    def boom(**kwargs):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(services, "_install_manifest", boom)
    with pytest.raises(services.SolutionTemplateError):
        wizard.create(_crm_selection(), workspace_id=ws, actor_id=None)
    assert DomainEvent.objects.filter(
        aggregate_type="solution_wizard", event_type="solution.wizard.failed").exists()


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_options_endpoint(workspace):
    c, _ = _client(workspace, "member")
    resp = c.get(f"{BASE}/options/")
    assert resp.status_code == 200
    body = resp.json()
    type_keys = {t["key"] for t in body["solution_types"]}
    assert {"crm", "hr", "procurement", "custom"} <= type_keys
    industry_keys = {i["key"] for i in body["industries"]}
    assert "healthcare" in industry_keys
    assert "business_objects" in body["library"]


@pytest.mark.django_db
def test_resolve_endpoint(workspace):
    c, _ = _client(workspace, "member")
    resp = c.post(f"{BASE}/resolve/", {"business_objects": ["contact"]}, format="json")
    assert resp.status_code == 200
    assert "customer" in resp.json()["resolved_objects"]


@pytest.mark.django_db
def test_preview_endpoint_does_not_install(workspace):
    c, _ = _client(workspace, "member")
    resp = c.post(f"{BASE}/preview/", _crm_selection(), format="json")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["summary"]["entities"] == 3
    assert not EntityDefinition.objects.filter(
        workspace_id=workspace.id, slug="customer").exists()


@pytest.mark.django_db
def test_member_cannot_create_admin_can(workspace):
    cm, _ = _client(workspace, "member", "m@e.com")
    assert cm.post(f"{BASE}/create/", _crm_selection(), format="json").status_code == 403

    ca, _ = _client(workspace, "admin", "a@e.com")
    resp = ca.post(f"{BASE}/create/", _crm_selection(), format="json")
    assert resp.status_code == 201
    assert resp.json()["solution_slug"] == "sales_crm"
    assert EntityDefinition.objects.filter(
        workspace_id=workspace.id, slug="customer").exists()
    assert Application.objects.filter(workspace_id=workspace.id, slug="sales_crm").exists()
