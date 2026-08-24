"""Shared fixtures for SLA tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.sla.models import BusinessHours, SLAPolicy
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
WEEK = {d: {"start": "09:00", "end": "17:00"} for d in ("mon", "tue", "wed", "thu", "fri")}


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="sla@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="priority",
                                    name="Priority", field_type="text", is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def business_hours(ws):
    def _make(holidays=None, tz="UTC"):
        return BusinessHours.objects.create(
            workspace_id=ws.id, name="Default", timezone=tz, schedule=WEEK,
            holidays=holidays or [])
    return _make


@pytest.fixture
def make_policy(ws, lead):
    n = {"i": 0}

    def _make(targets, applies_when="", escalation=None):
        n["i"] += 1
        return SLAPolicy.objects.create(
            workspace_id=ws.id, name=f"P{n['i']}", slug=f"p{n['i']}", entity_id=lead.id,
            applies_when_nql=applies_when, targets=targets,
            escalation_actions=escalation or [], is_active=True)
    return _make


@pytest.fixture
def client(ws, user, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c
