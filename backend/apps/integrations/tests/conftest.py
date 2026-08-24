"""Shared fixtures for integrations tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.integrations.models import HTTPConnector, WebhookSubscription
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="int@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def subscription(ws):
    def _make(event_types=None, signing_secret_ref="", max_retries=3):
        return WebhookSubscription.objects.create(
            workspace_id=ws.id, name="WH", target_url="https://hook.example/x",
            event_types=event_types or [], signing_secret_ref=signing_secret_ref,
            status="active", max_retries=max_retries)
    return _make


@pytest.fixture
def connector(ws):
    def _make(auth_type="none", auth_config=None):
        return HTTPConnector.objects.create(
            workspace_id=ws.id, name="C", slug="c", base_url="https://api.example",
            auth_type=auth_type, auth_config=auth_config or {})
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
