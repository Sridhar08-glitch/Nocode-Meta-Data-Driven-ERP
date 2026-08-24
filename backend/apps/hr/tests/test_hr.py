"""
HR Solution (Phase P2.7) — framework provisioning of the full HCM stack + the thin native
employee lifecycle (numbering, hire, leave approval with balance maths, promote/transfer/
offboard) and audit. Proves a complete HR platform is ~all framework.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.eventstore.models import DomainEvent
from apps.hr.blueprint import build_hr_manifest, seed_hr_template
from apps.hr.services import HRService
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
BASE = "/api/v1/hr"


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
    return st.install(template_id=seed_hr_template().id, workspace_id=ws, installed_by=None)


# ── framework provisioning ───────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_hr_manifest()) == []


@pytest.mark.django_db
def test_seed_creates_published_system_template():
    tpl = seed_hr_template()
    assert tpl.slug == "hr" and tpl.is_system and tpl.is_published
    seed_hr_template()
    assert SolutionTemplate.objects.filter(slug="hr").count() == 1


@pytest.mark.django_db
def test_install_provisions_full_hr_solution():
    ws = uuid.uuid4()
    _install(ws)
    for slug in ["branch", "department", "candidate", "interview", "offer", "employee",
                 "attendance_record", "leave_request", "performance_review", "promotion",
                 "transfer", "exit_request"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert EntityDefinition.objects.filter(workspace_id=ws).count() == 28
    for wf in ["hiring_workflow", "leave_approval", "offboarding_workflow"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    assert Role.objects.filter(workspace_id=ws, slug="hr_administrator").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 2
    assert Application.objects.filter(workspace_id=ws, slug="hr").exists()


# ── numbering ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_create_documents_allocate_numbers():
    ws = uuid.uuid4()
    _install(ws)
    cand = HRService.create_document(
        workspace_id=ws, entity_slug="candidate", data={"last_name": "Doe", "status": "new"})
    emp = HRService.create_document(
        workspace_id=ws, entity_slug="employee", data={"last_name": "Roe", "status": "active"})
    assert cand["number"] == "CAN-000001"
    assert emp["number"] == "EMP-000001"
    assert DomainEvent.objects.filter(event_type="hr.candidate.created").exists()


# ── recruitment → employee lifecycle ──────────────────────────────────────────
@pytest.mark.django_db
def test_hire_candidate_creates_employee():
    ws = uuid.uuid4()
    _install(ws)
    cand = HRService.create_document(
        workspace_id=ws, entity_slug="candidate",
        data={"first_name": "Ada", "last_name": "Lovelace", "status": "offer"})
    result = HRService.hire_candidate(workspace_id=ws, record_id=cand["id"])
    assert result["candidate"]["status"] == "hired"
    assert result["employee"]["number"] == "EMP-000001"
    assert result["employee"]["last_name"] == "Lovelace"
    assert DomainEvent.objects.filter(event_type="hr.employee.created").exists()


# ── leave approval with balance maths (the native calc) ──────────────────────
@pytest.mark.django_db
def test_approve_leave_decrements_balance():
    ws = uuid.uuid4()
    _install(ws)
    emp = HRService.create_document(
        workspace_id=ws, entity_slug="employee", data={"last_name": "Doe", "status": "active"})
    bal = HRService.create_document(
        workspace_id=ws, entity_slug="leave_balance",
        data={"employee": emp["id"], "allocated": "20", "used": "5", "remaining": "15"})
    req = HRService.create_document(
        workspace_id=ws, entity_slug="leave_request",
        data={"employee": emp["id"], "leave_balance": bal["id"], "days": "3",
              "status": "pending"})

    approved = HRService.approve_leave(workspace_id=ws, record_id=req["id"])
    assert approved["status"] == "approved"
    assert DomainEvent.objects.filter(event_type="hr.leave.approved").exists()

    from apps.records.services import RecordService, resolve_entity
    from apps.solution_templates.documents import system_member
    bal_after = RecordService.retrieve_record(
        workspace_id=ws, member=system_member(None),
        entity=resolve_entity(ws, "leave_balance"), record_id=bal["id"])
    assert float(bal_after["used"]) == 8.0       # 5 + 3
    assert float(bal_after["remaining"]) == 12.0  # 20 - 8


# ── promote / transfer / offboard ─────────────────────────────────────────────
@pytest.mark.django_db
def test_promote_transfer_offboard_emit_events():
    ws = uuid.uuid4()
    _install(ws)
    emp = HRService.create_document(
        workspace_id=ws, entity_slug="employee", data={"last_name": "Doe", "status": "active"})
    # position/department are lookup (uuid) columns — use valid UUIDs (PG enforces the type).
    new_pos, new_dep = str(uuid.uuid4()), str(uuid.uuid4())
    HRService.promote_employee(workspace_id=ws, record_id=emp["id"], new_position=new_pos)
    HRService.transfer_employee(workspace_id=ws, record_id=emp["id"], new_department=new_dep)
    off = HRService.offboard_employee(workspace_id=ws, record_id=emp["id"])
    assert off["status"] == "terminated"
    for ev in ["hr.employee.promoted", "hr.employee.transferred", "hr.employee.offboarded"]:
        assert DomainEvent.objects.filter(event_type=ev).exists(), ev


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_setup_requires_admin(workspace):
    _install(workspace.id)
    cm, _ = _client(workspace, "member", "m@e.com")
    assert cm.post(f"{BASE}/setup/").status_code == 403
    ca, _ = _client(workspace, "admin", "a@e.com")
    assert ca.post(f"{BASE}/setup/").status_code == 200


@pytest.mark.django_db
def test_create_candidate_and_hire_via_api(workspace):
    _install(workspace.id)
    ca, _ = _client(workspace, "admin")
    cand = ca.post(f"{BASE}/candidate/", {"last_name": "Doe", "status": "offer"}, format="json")
    assert cand.status_code == 201
    assert cand.json()["number"] == "CAN-000001"

    resp = ca.post(f"{BASE}/candidates/{cand.json()['id']}/hire/")
    assert resp.status_code == 200
    assert resp.json()["employee"]["number"] == "EMP-000001"
