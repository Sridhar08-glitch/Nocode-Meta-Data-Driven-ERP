"""Shared fixtures for notifications tests."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.notifications.models import NotificationTemplate
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="n@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


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
def template(ws):
    def _make(slug="welcome", channel="in_app", subject="Hi ${actor_name}",
              body="Welcome ${actor_name} to ${workspace_name}"):
        return NotificationTemplate.objects.create(
            workspace_id=ws.id, slug=slug, name=slug.title(), channel=channel,
            subject_template=subject, body_template=body)
    return _make
