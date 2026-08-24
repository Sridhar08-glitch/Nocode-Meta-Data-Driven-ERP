"""Shared fixtures for activity/comment tests."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="a@acme.com", password=PW,
                                    full_name="Ada Lovelace", is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    for slug, ftype in [("name", "text"), ("status", "text"), ("ssn", "text")]:
        SchemaRegistryService.add_field(
            workspace_id=ws.id, entity_slug="lead", slug=slug, name=slug.title(),
            field_type=ftype, is_promoted=True)
    ent.refresh_from_db()
    return ent


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


@pytest.fixture
def make_event(ws):
    from apps.eventstore.models import DomainEvent

    def _make(event_type, *, record_id=None, entity_id=None, entity_slug="lead",
              payload=None, actor_id=None, aggregate_type="record"):
        rid = record_id or uuid.uuid4()
        data = {"entity_slug": entity_slug, "record_id": str(rid)}
        if entity_id is not None:
            data["entity_id"] = str(entity_id)
        if payload:
            data.update(payload)
        return DomainEvent.objects.create(
            workspace_id=ws.id, event_type=event_type, aggregate_type=aggregate_type,
            aggregate_id=rid, version=1, payload=data,
            actor_id=actor_id or uuid.uuid4())
    return _make
