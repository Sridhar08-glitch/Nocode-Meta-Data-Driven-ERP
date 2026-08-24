"""
Workspace invitation lifecycle (P2.17 Batch 3): pending → accept / reject /
resend / cancel / expire. Driven through the real HTTP API with real tokens.
"""
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceInvitation, WorkspaceMember

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


def _token_from_last_email():
    return re.search(r"token=([A-Za-z0-9_\-]+)", mail.outbox[-1].body).group(1)


@pytest.mark.django_db
class TestInvitationLifecycle:
    def test_invite_creates_pending_and_emails(self):
        owner, ws = _owner_ws()
        mail.outbox = []
        r = _client(owner).post(f"{URL}{ws.slug}/invitations/",
                                {"email": "hire@acme.test", "role": "member"}, format="json")
        assert r.status_code == 201 and r.data["status"] == "pending"
        assert mail.outbox and "hire@acme.test" in mail.outbox[-1].to
        # no membership exists yet — invitation is pending, not active
        assert not WorkspaceMember.objects.filter(
            workspace=ws, user__email="hire@acme.test").exists()

    def test_existing_user_accepts(self):
        owner, ws = _owner_ws()
        invitee = User.objects.create_user(email="x@acme.test", password=PW, is_verified=True)
        mail.outbox = []
        _client(owner).post(f"{URL}{ws.slug}/invitations/",
                            {"email": "x@acme.test", "role": "admin"}, format="json")
        token = _token_from_last_email()
        r = _client(invitee).post(f"{URL}invitations/accept/", {"token": token}, format="json")
        assert r.status_code == 200 and r.data["role"] == "admin"
        m = WorkspaceMember.objects.get(workspace=ws, user=invitee)
        assert m.status == "active" and m.role == "admin"
        # invitation marked accepted
        assert WorkspaceInvitation.objects.get(workspace=ws, email="x@acme.test").status == "accepted"

    def test_new_user_journey_register_then_accept(self):
        owner, ws = _owner_ws()
        mail.outbox = []
        _client(owner).post(f"{URL}{ws.slug}/invitations/",
                            {"email": "new@acme.test"}, format="json")
        invite_token = _token_from_last_email()
        # new user signs up + verifies with the invited email
        anon = APIClient()
        anon.post("/api/v1/auth/register/",
                  {"email": "new@acme.test", "password": PW, "full_name": "New"}, format="json")
        anon.post("/api/v1/auth/verify-email/", {"token": _token_from_last_email()}, format="json")
        login = anon.post("/api/v1/auth/login/",
                          {"email": "new@acme.test", "password": PW}, format="json")
        invitee = _client(User.objects.get(email="new@acme.test"))
        invitee.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        r = invitee.post(f"{URL}invitations/accept/", {"token": invite_token}, format="json")
        assert r.status_code == 200
        assert WorkspaceMember.objects.filter(
            workspace=ws, user__email="new@acme.test", status="active").exists()

    def test_wrong_email_cannot_accept(self):
        owner, ws = _owner_ws()
        other = User.objects.create_user(email="other@acme.test", password=PW, is_verified=True)
        mail.outbox = []
        _client(owner).post(f"{URL}{ws.slug}/invitations/",
                            {"email": "target@acme.test"}, format="json")
        token = _token_from_last_email()
        assert _client(other).post(f"{URL}invitations/accept/",
                                   {"token": token}, format="json").status_code == 403

    def test_reject(self):
        owner, ws = _owner_ws()
        invitee = User.objects.create_user(email="r@acme.test", password=PW, is_verified=True)
        mail.outbox = []
        _client(owner).post(f"{URL}{ws.slug}/invitations/", {"email": "r@acme.test"}, format="json")
        token = _token_from_last_email()
        assert _client(invitee).post(f"{URL}invitations/reject/",
                                     {"token": token}, format="json").status_code == 200
        assert WorkspaceInvitation.objects.get(workspace=ws, email="r@acme.test").status == "rejected"

    def test_cancel_then_accept_fails(self):
        owner, ws = _owner_ws()
        invitee = User.objects.create_user(email="c@acme.test", password=PW, is_verified=True)
        mail.outbox = []
        inv = _client(owner).post(f"{URL}{ws.slug}/invitations/",
                                  {"email": "c@acme.test"}, format="json").data
        token = _token_from_last_email()
        assert _client(owner).post(
            f"{URL}{ws.slug}/invitations/{inv['id']}/cancel/").status_code == 200
        assert _client(invitee).post(f"{URL}invitations/accept/",
                                     {"token": token}, format="json").status_code == 400

    def test_expired_invitation_rejected(self):
        owner, ws = _owner_ws()
        invitee = User.objects.create_user(email="e@acme.test", password=PW, is_verified=True)
        mail.outbox = []
        _client(owner).post(f"{URL}{ws.slug}/invitations/", {"email": "e@acme.test"}, format="json")
        token = _token_from_last_email()
        WorkspaceInvitation.objects.filter(workspace=ws, email="e@acme.test").update(
            expires_at=timezone.now() - timedelta(hours=1))
        assert _client(invitee).post(f"{URL}invitations/accept/",
                                     {"token": token}, format="json").status_code == 400
        assert WorkspaceInvitation.objects.get(workspace=ws, email="e@acme.test").status == "expired"

    def test_resend_refreshes_token(self):
        owner, ws = _owner_ws()
        mail.outbox = []
        inv = _client(owner).post(f"{URL}{ws.slug}/invitations/",
                                  {"email": "rs@acme.test"}, format="json").data
        first = _token_from_last_email()
        r = _client(owner).post(f"{URL}{ws.slug}/invitations/{inv['id']}/resend/")
        assert r.status_code == 200
        second = _token_from_last_email()
        assert first != second  # token rotated

    def test_non_admin_cannot_invite(self):
        owner, ws = _owner_ws()
        member = User.objects.create_user(email="mm@acme.test", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=member, role="member", status="active")
        assert _client(member).post(f"{URL}{ws.slug}/invitations/",
                                    {"email": "z@acme.test"}, format="json").status_code == 403

    def test_invite_existing_active_member_rejected(self):
        owner, ws = _owner_ws()
        r = _client(owner).post(f"{URL}{ws.slug}/invitations/",
                                {"email": owner.email}, format="json")
        assert r.status_code == 400
