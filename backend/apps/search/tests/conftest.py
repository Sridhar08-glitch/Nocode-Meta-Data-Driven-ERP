"""Shared fixtures for search tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.search.services import SearchService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="s@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


def _entity(ws, slug, fields=("name", "notes")):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug=slug, name=slug.title(), plural_name=slug.title() + "s")
    for f in fields:
        SchemaRegistryService.add_field(
            workspace_id=ws.id, entity_slug=slug, slug=f, name=f.title(),
            field_type="text", is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def lead(ws):
    return _entity(ws, "lead")


@pytest.fixture
def deal(ws):
    return _entity(ws, "deal")


@pytest.fixture
def indexed(ws, member, lead, deal):
    """Two entities with records + search indexes."""
    RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                data={"name": "Acme Corporation", "notes": "hot lead"})
    RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                data={"name": "Globex", "notes": "cold"})
    RecordService.create_record(workspace_id=ws.id, member=member, entity=deal,
                                data={"name": "Acme renewal", "notes": "q3"})
    SearchService.create_index(entity=lead, workspace_id=ws.id,
                               indexed_field_slugs=["name", "notes"])
    SearchService.create_index(entity=deal, workspace_id=ws.id,
                               indexed_field_slugs=["name", "notes"])
    return lead, deal


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
