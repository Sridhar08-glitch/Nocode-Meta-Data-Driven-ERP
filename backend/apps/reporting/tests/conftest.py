"""Shared fixtures for reporting tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.records.services import RecordService
from apps.reporting.models import Report
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="rep@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    for slug, ftype in [("name", "text"), ("status", "text"), ("value", "decimal")]:
        SchemaRegistryService.add_field(
            workspace_id=ws.id, entity_slug="lead", slug=slug, name=slug.title(),
            field_type=ftype, is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def leads(ws, member, lead):
    rows = [("A", "open", 100), ("B", "open", 200), ("C", "won", 50)]
    for name, status, value in rows:
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": name, "status": status, "value": value})
    return lead


@pytest.fixture
def make_report(ws):
    def _make(slug="r1", report_type="table", nql_ast=None, display_config=None):
        return Report.objects.create(
            workspace_id=ws.id, name=slug.upper(), slug=slug, report_type=report_type,
            nql_ast=nql_ast or {"entity": "lead"}, display_config=display_config or {})
    return _make


@pytest.fixture
def client(ws, user, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


def make_client(workspace, email, role="admin"):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=u, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return u, c
