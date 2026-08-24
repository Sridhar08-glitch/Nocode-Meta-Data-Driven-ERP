"""
Account self-service lifecycle (P2.17): authenticated change-password,
change-email + verify-new-email, resend-verification. Driven through the real HTTP
API with real email tokens read from the outbox.
"""
import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import EmailVerificationToken, User

PW = "Sup3rStr0ng!pw"
NEW_PW = "N3wStr0ngerPwd!"


def _auth(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
    return c


def _token_from_last_email():
    return re.search(r"token=([A-Za-z0-9_\-]+)", mail.outbox[-1].body).group(1)


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@example.com", password=PW, is_verified=True)


@pytest.mark.django_db
class TestChangePassword:
    def test_wrong_current_rejected(self, user):
        r = _auth(user).post("/api/v1/auth/change-password/",
                             {"current_password": "wrong", "password": NEW_PW}, format="json")
        assert r.status_code == 400

    def test_weak_new_password_rejected(self, user):
        r = _auth(user).post("/api/v1/auth/change-password/",
                             {"current_password": PW, "password": "123"}, format="json")
        assert r.status_code == 400

    def test_change_succeeds_and_emails_notice(self, user):
        mail.outbox = []
        r = _auth(user).post("/api/v1/auth/change-password/",
                             {"current_password": PW, "password": NEW_PW}, format="json")
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.check_password(NEW_PW) and not user.check_password(PW)
        assert any("password" in m.subject.lower() for m in mail.outbox)

    def test_revokes_other_sessions(self, db):
        c = APIClient()
        mail.outbox = []
        c.post("/api/v1/auth/register/",
               {"email": "s@example.com", "password": PW, "full_name": "S"}, format="json")
        c.post("/api/v1/auth/verify-email/", {"token": _token_from_last_email()}, format="json")
        login = c.post("/api/v1/auth/login/",
                       {"email": "s@example.com", "password": PW}, format="json")
        access, refresh = login.data["access"], login.data["refresh"]
        auth = APIClient()
        auth.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert auth.post("/api/v1/auth/change-password/",
                         {"current_password": PW, "password": NEW_PW},
                         format="json").status_code == 200
        # the old session's refresh family is revoked → refresh now fails
        assert APIClient().post("/api/v1/auth/refresh/",
                                {"refresh": refresh}, format="json").status_code == 401

    def test_requires_auth(self):
        assert APIClient().post("/api/v1/auth/change-password/",
                                {"current_password": PW, "password": NEW_PW},
                                format="json").status_code in (401, 403)


@pytest.mark.django_db
class TestChangeEmail:
    def test_change_email_flow(self, user):
        mail.outbox = []
        r = _auth(user).post("/api/v1/auth/change-email/",
                             {"new_email": "new@example.com", "password": PW}, format="json")
        assert r.status_code == 200
        assert mail.outbox and "new@example.com" in mail.outbox[-1].to
        # email is NOT changed until the link is confirmed
        user.refresh_from_db()
        assert user.email == "u@example.com"
        # confirm via the standard verify-email endpoint
        r = APIClient().post("/api/v1/auth/verify-email/",
                             {"token": _token_from_last_email()}, format="json")
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.email == "new@example.com"

    def test_wrong_password_rejected(self, user):
        r = _auth(user).post("/api/v1/auth/change-email/",
                             {"new_email": "x@example.com", "password": "nope"}, format="json")
        assert r.status_code == 400

    def test_taken_email_is_generic_and_changes_nothing(self, user):
        User.objects.create_user(email="taken@example.com", password=PW, is_verified=True)
        mail.outbox = []
        r = _auth(user).post("/api/v1/auth/change-email/",
                             {"new_email": "taken@example.com", "password": PW}, format="json")
        assert r.status_code == 200  # does not reveal that the address exists
        assert not EmailVerificationToken.objects.filter(new_email="taken@example.com").exists()
        user.refresh_from_db()
        assert user.email == "u@example.com"

    def test_same_email_rejected(self, user):
        r = _auth(user).post("/api/v1/auth/change-email/",
                             {"new_email": "u@example.com", "password": PW}, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestResendVerification:
    def test_resends_for_unverified(self, db):
        User.objects.create_user(email="unv@example.com", password=PW, is_verified=False)
        mail.outbox = []
        r = APIClient().post("/api/v1/auth/resend-verification/",
                             {"email": "unv@example.com"}, format="json")
        assert r.status_code == 200 and mail.outbox

    def test_silent_for_verified_user(self, db):
        User.objects.create_user(email="ver@example.com", password=PW, is_verified=True)
        mail.outbox = []
        r = APIClient().post("/api/v1/auth/resend-verification/",
                             {"email": "ver@example.com"}, format="json")
        assert r.status_code == 200 and not mail.outbox

    def test_silent_for_unknown_email(self, db):
        mail.outbox = []
        r = APIClient().post("/api/v1/auth/resend-verification/",
                             {"email": "nobody@example.com"}, format="json")
        assert r.status_code == 200 and not mail.outbox
