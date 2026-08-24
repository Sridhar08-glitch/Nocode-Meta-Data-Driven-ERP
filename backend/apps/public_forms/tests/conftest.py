"""Shared fixtures for public forms tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import FormDefinition
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="forms@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True,
                                    is_required=True)
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="message",
                                    name="Message", field_type="text", is_promoted=True)
    return SchemaRegistryService.get_entity(workspace_id=ws.id, slug="lead")


@pytest.fixture
def form(ws, lead):
    return FormDefinition.objects.create(
        workspace_id=ws.id, entity_id=lead.id, name="Contact", is_public=True,
        layout=[], settings={})


@pytest.fixture
def client(ws, user, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c
