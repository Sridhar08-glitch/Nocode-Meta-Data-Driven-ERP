"""Shared fixtures for import/export tests."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="imp@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True,
                                    is_required=True)
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="value",
                                    name="Value", field_type="decimal", is_promoted=True)
    ent.refresh_from_db()
    return ent


def csv_file(content: str, name="data.csv"):
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


def xlsx_file(rows, name="data.xlsx"):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(
        name, buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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
