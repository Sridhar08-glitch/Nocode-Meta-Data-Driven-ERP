"""
CRM Solution (Phase P2.6) — framework provisioning + the thin native pipeline lifecycle
(numbering, qualify, win/lose, activity completion) and audit. Proves CRM is ~all framework.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.crm.blueprint import build_crm_manifest, seed_crm_template
from apps.crm.services import CRMService
from apps.eventstore.models import DomainEvent
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.reporting.models import Dashboard
from apps.solution_templates import services as st
from apps.solution_templates.models import SolutionTemplate
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import WorkflowDefinition

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/crm"


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


def _install(ws):
    tpl = seed_crm_template()
    return st.install(template_id=tpl.id, workspace_id=ws, installed_by=None)


# ── framework provisioning ───────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_crm_manifest()) == []


@pytest.mark.django_db
def test_seed_creates_published_system_template():
    tpl = seed_crm_template()
    assert tpl.slug == "crm" and tpl.is_system and tpl.is_published
    seed_crm_template()
    assert SolutionTemplate.objects.filter(slug="crm").count() == 1


@pytest.mark.django_db
def test_install_provisions_full_crm_solution():
    ws = uuid.uuid4()
    _install(ws)
    for slug in ["lead", "account", "contact", "opportunity", "activity"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["lead_assignment", "lead_qualification", "opportunity_review",
               "opportunity_closure"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    assert Role.objects.filter(workspace_id=ws, slug="sales_manager").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 2
    assert Application.objects.filter(workspace_id=ws, slug="crm").exists()


# ── numbering ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_create_documents_allocate_numbers():
    ws = uuid.uuid4()
    _install(ws)
    lead = CRMService.create_document(
        workspace_id=ws, entity_slug="lead", data={"last_name": "Doe", "status": "new"})
    acc = CRMService.create_document(
        workspace_id=ws, entity_slug="account", data={"name": "Acme"})
    assert lead["number"] == "LEAD-000001"
    assert acc["number"] == "ACC-000001"
    assert DomainEvent.objects.filter(event_type="crm.lead.created").count() == 1


# ── pipeline lifecycle ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_qualify_lead_creates_opportunity():
    ws = uuid.uuid4()
    _install(ws)
    lead = CRMService.create_document(
        workspace_id=ws, entity_slug="lead", data={"last_name": "Doe", "status": "new"})
    result = CRMService.qualify_lead(workspace_id=ws, record_id=lead["id"])
    assert result["lead"]["status"] == "qualified"
    assert result["opportunity"]["number"] == "OPP-000001"
    assert DomainEvent.objects.filter(event_type="crm.lead.qualified").exists()
    assert DomainEvent.objects.filter(event_type="crm.opportunity.created").exists()


@pytest.mark.django_db
def test_win_and_lose_opportunity_emit_events():
    ws = uuid.uuid4()
    _install(ws)
    o1 = CRMService.create_document(
        workspace_id=ws, entity_slug="opportunity", data={"stage": "negotiation"})
    won = CRMService.win_opportunity(
        workspace_id=ws, record_id=o1["id"], reason="best price")
    assert won["stage"] == "won" and won["close_reason"] == "best price"
    assert DomainEvent.objects.filter(event_type="crm.opportunity.won").exists()

    o2 = CRMService.create_document(
        workspace_id=ws, entity_slug="opportunity", data={"stage": "proposal"})
    lost = CRMService.lose_opportunity(workspace_id=ws, record_id=o2["id"], reason="budget")
    assert lost["stage"] == "lost"
    assert DomainEvent.objects.filter(event_type="crm.opportunity.lost").exists()


@pytest.mark.django_db
def test_complete_activity_emits_event():
    ws = uuid.uuid4()
    _install(ws)
    act = CRMService.create_document(
        workspace_id=ws, entity_slug="activity",
        data={"type": "call", "subject": "Intro call", "status": "open"})
    done = CRMService.complete_activity(workspace_id=ws, record_id=act["id"])
    assert done["status"] == "completed"
    assert DomainEvent.objects.filter(event_type="crm.activity.completed").exists()


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_setup_requires_admin(workspace):
    _install(workspace.id)
    cm, _ = _client(workspace, "member", "m@e.com")
    assert cm.post(f"{BASE}/setup/").status_code == 403
    ca, _ = _client(workspace, "admin", "a@e.com")
    assert ca.post(f"{BASE}/setup/").status_code == 200


@pytest.mark.django_db
def test_create_lead_and_qualify_via_api(workspace):
    _install(workspace.id)
    ca, _ = _client(workspace, "admin")
    lead = ca.post(f"{BASE}/lead/", {"last_name": "Doe", "status": "new"}, format="json")
    assert lead.status_code == 201
    assert lead.json()["number"] == "LEAD-000001"

    resp = ca.post(f"{BASE}/leads/{lead.json()['id']}/qualify/")
    assert resp.status_code == 200
    assert resp.json()["lead"]["status"] == "qualified"
    assert resp.json()["opportunity"]["number"] == "OPP-000001"
