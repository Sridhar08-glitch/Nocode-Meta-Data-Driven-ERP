"""
Workspace lifecycle (P2.17 Batch 4): archive / restore / soft-delete /
hard-delete-with-confirmation / retention purge. Driven through the real HTTP API.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.tenancy.services import PURGE_TTL, WorkspaceService

PW = "Sup3rStr0ng!pw"
URL = "/api/v1/workspaces/"


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
    return c


def _owner_ws(email="owner@acme.test", slug="acme"):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    ws = Workspace.objects.create(name="Acme", slug=slug, is_active=True, owner=u)
    WorkspaceMember.objects.create(workspace=ws, user=u, role="owner", status="active")
    return u, ws


@pytest.mark.django_db
class TestWorkspaceLifecycle:
    def test_archive_and_restore(self):
        owner, ws = _owner_ws()
        assert _client(owner).post(f"{URL}{ws.slug}/archive/").status_code == 200
        ws.refresh_from_db()
        assert ws.is_active is False
        # archived workspace drops out of the active listing
        active = _client(owner).get(URL).data
        assert all(w["slug"] != ws.slug for w in active)
        # but shows under ?archived=true
        archived = _client(owner).get(f"{URL}?archived=true").data
        assert any(w["slug"] == ws.slug for w in archived)
        # restore
        assert _client(owner).post(f"{URL}{ws.slug}/restore/").status_code == 200
        ws.refresh_from_db()
        assert ws.is_active is True

    def test_soft_delete_then_restore(self):
        owner, ws = _owner_ws()
        assert _client(owner).delete(f"{URL}{ws.slug}/").status_code == 204
        ws.refresh_from_db()
        assert ws.deleted_at is not None and ws.is_active is False
        assert _client(owner).post(f"{URL}{ws.slug}/restore/").status_code == 200
        ws.refresh_from_db()
        assert ws.deleted_at is None and ws.is_active is True

    def test_hard_delete_with_confirmation(self):
        owner, ws = _owner_ws()
        req = _client(owner).post(f"{URL}{ws.slug}/delete-permanently/")
        assert req.status_code == 200
        token = req.data["confirmation_token"]
        # wrong token rejected
        assert _client(owner).post(f"{URL}{ws.slug}/delete-permanently/confirm/",
                                   {"token": "bogus"}, format="json").status_code == 400
        assert Workspace.objects.filter(slug=ws.slug).exists()
        # correct token purges
        assert _client(owner).post(f"{URL}{ws.slug}/delete-permanently/confirm/",
                                   {"token": token}, format="json").status_code == 204
        assert not Workspace.objects.filter(slug=ws.slug).exists()
        # FK-cascaded identity rows gone too
        assert not WorkspaceMember.objects.filter(workspace_id=ws.id).exists()

    def test_hard_delete_token_expiry(self):
        owner, ws = _owner_ws()
        token = _client(owner).post(f"{URL}{ws.slug}/delete-permanently/").data["confirmation_token"]
        ws.refresh_from_db()
        purge = dict(ws.settings)["_purge"]
        purge["expires"] = (timezone.now() - timedelta(minutes=1)).isoformat()
        ws.settings["_purge"] = purge
        ws.save(update_fields=["settings"])
        assert _client(owner).post(f"{URL}{ws.slug}/delete-permanently/confirm/",
                                   {"token": token}, format="json").status_code == 400
        assert Workspace.objects.filter(slug=ws.slug).exists()

    def test_only_owner_can_archive_or_delete(self):
        owner, ws = _owner_ws()
        admin = User.objects.create_user(email="adm@acme.test", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")
        assert _client(admin).post(f"{URL}{ws.slug}/archive/").status_code == 403
        assert _client(admin).delete(f"{URL}{ws.slug}/").status_code == 403
        assert _client(admin).post(f"{URL}{ws.slug}/delete-permanently/").status_code == 403

    def test_retention_purge_removes_expired(self):
        owner, ws = _owner_ws()
        ws.deleted_at = timezone.now() - PURGE_TTL - timedelta(days=1)
        ws.is_active = False
        ws.save(update_fields=["deleted_at", "is_active"])
        purged = WorkspaceService.purge_expired_workspaces()
        assert purged == 1
        assert not Workspace.objects.filter(slug=ws.slug).exists()

    def test_retention_keeps_fresh_soft_deletes(self):
        owner, ws = _owner_ws()
        ws.deleted_at = timezone.now() - timedelta(days=1)  # recent
        ws.save(update_fields=["deleted_at"])
        assert WorkspaceService.purge_expired_workspaces() == 0
        assert Workspace.objects.filter(slug=ws.slug).exists()
