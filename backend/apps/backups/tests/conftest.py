"""Shared fixtures for backups tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _make_lead(workspace_id):
    SchemaRegistryService.create_entity(
        workspace_id=workspace_id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=workspace_id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=workspace_id, entity_slug="lead", slug="email",
                                    name="Email", field_type="text", is_promoted=True)
    return SchemaRegistryService.get_entity(workspace_id=workspace_id, slug="lead")


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="bk@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    return _make_lead(ws.id)


@pytest.fixture
def target_ws(db):
    ws = Workspace.objects.create(name="Restore Target", slug="restore-target", is_active=True)
    _make_lead(ws.id)
    return ws


@pytest.fixture
def client(ws, user, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c
