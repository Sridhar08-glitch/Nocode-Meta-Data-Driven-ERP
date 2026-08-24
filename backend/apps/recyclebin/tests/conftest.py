"""Shared fixtures for recycle bin tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="rb@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def deleted_record(ws, member, lead):
    """Create + soft-delete a record, returning (record_id, recycle entry)."""
    from apps.recyclebin.models import RecycleBinEntry

    def _make(name="Doomed"):
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"name": name})
        RecordService.delete_record(workspace_id=ws.id, member=member, entity=lead,
                                    record_id=rec["id"])
        entry = RecycleBinEntry.objects.get(workspace_id=ws.id, record_id=rec["id"])
        return rec["id"], entry
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
