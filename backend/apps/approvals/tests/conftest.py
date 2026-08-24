"""Shared fixtures for approvals tests."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.approvals.models import ApprovalProcess
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _user(ws, email, role="member"):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=u, role=role, status="active")
    return u


@pytest.fixture
def requester(ws):
    return _user(ws, "req@acme.com", role="admin")


@pytest.fixture
def approver_a(ws):
    return _user(ws, "a@acme.com")


@pytest.fixture
def approver_b(ws):
    return _user(ws, "b@acme.com")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="status",
                                    name="Status", field_type="text", is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def make_process(ws, lead):
    n = {"i": 0}

    def _make(levels, on_approve=None, on_reject=None):
        n["i"] += 1
        return ApprovalProcess.objects.create(
            workspace_id=ws.id, name=f"P{n['i']}", slug=f"p{n['i']}", entity_id=lead.id,
            levels=levels, on_approve_actions=on_approve or [],
            on_reject_actions=on_reject or [])
    return _make


@pytest.fixture
def record_id():
    return uuid.uuid4()


def client_for(ws, user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c
