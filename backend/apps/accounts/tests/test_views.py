from unittest import mock

import pyotp
import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.crypto import encrypt_secret, hash_token
from apps.accounts.models import (
    EmailVerificationToken,
    LoginHistory,
    OAuthAccount,
    PasswordResetToken,
    RefreshTokenFamily,
    User,
)

STRONG_PW = "Sup3rStr0ng!pw"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def verified_user(db):
    return User.objects.create_user(email="alice@example.com", password=STRONG_PW, is_verified=True)


def auth(client, user, workspace_id=None):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user, workspace_id)}")
    return client


def enable_mfa(user):
    secret = pyotp.random_base32()
    user.mfa_secret = encrypt_secret(secret)
    user.mfa_enabled = True
    user.save(update_fields=["mfa_secret", "mfa_enabled"])
    return secret


# ── Registration + verification ─────────────────────────────────────────────
@pytest.mark.django_db
class TestRegisterVerify:
    def test_register_sends_verification(self, api):
        r = api.post(reverse("accounts:register"),
                     {"email": "bob@example.com", "password": STRONG_PW, "full_name": "Bob"}, format="json")
        assert r.status_code == 201
        u = User.objects.get(email="bob@example.com")
        assert u.is_verified is False
        assert EmailVerificationToken.objects.filter(user=u).count() == 1
        assert len(mail.outbox) == 1

    def test_register_duplicate(self, api, verified_user):
        r = api.post(reverse("accounts:register"),
                     {"email": verified_user.email, "password": STRONG_PW}, format="json")
        assert r.status_code == 409

    def test_register_weak_password(self, api):
        r = api.post(reverse("accounts:register"),
                     {"email": "weak@example.com", "password": "123"}, format="json")
        assert r.status_code == 400

    def test_verify_email_flow(self, api):
        api.post(reverse("accounts:register"),
                 {"email": "carol@example.com", "password": STRONG_PW}, format="json")
        u = User.objects.get(email="carol@example.com")
        # Re-create a known raw token (the raw value is not stored, so mint one directly)
        from apps.accounts import services
        raw, _ = services.create_email_verification_token(u)
        r = api.post(reverse("accounts:verify-email"), {"token": raw}, format="json")
        assert r.status_code == 200
        assert "access" in r.data and "refresh" in r.data
        u.refresh_from_db()
        assert u.is_verified is True

    def test_verify_email_invalid(self, api):
        r = api.post(reverse("accounts:verify-email"), {"token": "nope"}, format="json")
        assert r.status_code == 400


# ── Login + refresh + logout ────────────────────────────────────────────────
@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api, verified_user):
        r = api.post(reverse("accounts:login"),
                     {"email": verified_user.email, "password": STRONG_PW}, format="json")
        assert r.status_code == 200
        assert "access" in r.data
        assert LoginHistory.objects.filter(user=verified_user, success=True).count() == 1

    def test_login_wrong_password_records_failure(self, api, verified_user):
        r = api.post(reverse("accounts:login"),
                     {"email": verified_user.email, "password": "wrongpassword!"}, format="json")
        assert r.status_code == 401
        assert LoginHistory.objects.filter(success=False, failure_reason="invalid_credentials").count() == 1

    def test_login_unverified(self, api, db):
        User.objects.create_user(email="unv@example.com", password=STRONG_PW, is_verified=False)
        r = api.post(reverse("accounts:login"),
                     {"email": "unv@example.com", "password": STRONG_PW}, format="json")
        assert r.status_code == 403

    def test_login_inactive(self, api, db):
        User.objects.create_user(email="ina@example.com", password=STRONG_PW, is_verified=True, is_active=False)
        r = api.post(reverse("accounts:login"),
                     {"email": "ina@example.com", "password": STRONG_PW}, format="json")
        assert r.status_code in (401, 403)

    def test_refresh_rotation(self, api, verified_user):
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        refresh = login.data["refresh"]
        r = api.post(reverse("accounts:refresh"), {"refresh": refresh}, format="json")
        assert r.status_code == 200
        assert r.data["refresh"] != refresh

    def test_refresh_reuse_detected(self, api, verified_user):
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        refresh = login.data["refresh"]
        api.post(reverse("accounts:refresh"), {"refresh": refresh}, format="json")
        r = api.post(reverse("accounts:refresh"), {"refresh": refresh}, format="json")
        assert r.status_code == 401

    def test_logout_revokes_family(self, api, verified_user):
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        refresh = login.data["refresh"]
        auth(api, verified_user)
        r = api.post(reverse("accounts:logout"), {"refresh": refresh}, format="json")
        assert r.status_code == 200
        fam = RefreshTokenFamily.objects.filter(user=verified_user).latest("created_at")
        assert not fam.is_active

    def test_logout_requires_auth(self, api):
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)


# ── Password reset ──────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPasswordReset:
    def test_request_existing(self, api, verified_user):
        r = api.post(reverse("accounts:password-reset-request"),
                     {"email": verified_user.email}, format="json")
        assert r.status_code == 200
        assert PasswordResetToken.objects.filter(user=verified_user).count() == 1
        assert len(mail.outbox) == 1

    def test_request_nonexistent_no_leak(self, api, db):
        r = api.post(reverse("accounts:password-reset-request"),
                     {"email": "ghost@example.com"}, format="json")
        assert r.status_code == 200
        assert PasswordResetToken.objects.count() == 0
        assert len(mail.outbox) == 0

    def test_confirm_resets_and_revokes(self, api, verified_user):
        from apps.accounts import services
        tokens.issue_refresh_token(verified_user)  # active session to be revoked
        raw, _ = services.create_password_reset_token(verified_user)
        r = api.post(reverse("accounts:password-reset-confirm"),
                     {"token": raw, "password": "Br4ndN3w!pass"}, format="json")
        assert r.status_code == 200
        verified_user.refresh_from_db()
        assert verified_user.check_password("Br4ndN3w!pass")
        assert RefreshTokenFamily.objects.filter(user=verified_user, is_active=True).count() == 0

    def test_confirm_invalid_token(self, api):
        r = api.post(reverse("accounts:password-reset-confirm"),
                     {"token": "bad", "password": "Br4ndN3w!pass"}, format="json")
        assert r.status_code == 400


# ── MFA ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestMfa:
    def test_setup_initiate_stores_encrypted(self, api, verified_user):
        auth(api, verified_user)
        r = api.post(reverse("accounts:mfa-setup-initiate"), {}, format="json")
        assert r.status_code == 200
        assert "secret" in r.data and "qr_uri" in r.data
        verified_user.refresh_from_db()
        # Stored secret is ciphertext, not the plaintext returned to the client.
        assert verified_user.mfa_secret and verified_user.mfa_secret != r.data["secret"]

    def test_setup_confirm_enables_and_returns_backup_codes(self, api, verified_user):
        auth(api, verified_user)
        init = api.post(reverse("accounts:mfa-setup-initiate"), {}, format="json")
        code = pyotp.TOTP(init.data["secret"]).now()
        r = api.post(reverse("accounts:mfa-setup-confirm"), {"code": code}, format="json")
        assert r.status_code == 200
        assert len(r.data["backup_codes"]) == 10
        verified_user.refresh_from_db()
        assert verified_user.mfa_enabled is True

    def test_setup_confirm_wrong_code(self, api, verified_user):
        auth(api, verified_user)
        api.post(reverse("accounts:mfa-setup-initiate"), {}, format="json")
        r = api.post(reverse("accounts:mfa-setup-confirm"), {"code": "000000"}, format="json")
        assert r.status_code == 400

    def test_login_with_mfa_required_then_totp(self, api, verified_user):
        secret = enable_mfa(verified_user)
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        assert login.data.get("mfa_required") is True
        mfa_token = login.data["mfa_token"]
        code = pyotp.TOTP(secret).now()
        r = api.post(reverse("accounts:login-mfa"), {"mfa_token": mfa_token, "code": code}, format="json")
        assert r.status_code == 200
        assert "access" in r.data

    def test_login_mfa_backup_code_consumed(self, api, verified_user):
        enable_mfa(verified_user)
        backup = "ABCDEFGHIJ"
        verified_user.mfa_backup_codes = [hash_token(backup)]
        verified_user.save(update_fields=["mfa_backup_codes"])
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        r = api.post(reverse("accounts:login-mfa"),
                     {"mfa_token": login.data["mfa_token"], "code": backup}, format="json")
        assert r.status_code == 200
        verified_user.refresh_from_db()
        assert verified_user.mfa_backup_codes == []

    def test_login_mfa_wrong_code(self, api, verified_user):
        enable_mfa(verified_user)
        login = api.post(reverse("accounts:login"),
                         {"email": verified_user.email, "password": STRONG_PW}, format="json")
        r = api.post(reverse("accounts:login-mfa"),
                     {"mfa_token": login.data["mfa_token"], "code": "000000"}, format="json")
        assert r.status_code == 401

    def test_disable_requires_password(self, api, verified_user):
        enable_mfa(verified_user)
        auth(api, verified_user)
        bad = api.post(reverse("accounts:mfa-disable"), {"password": "wrongpass!"}, format="json")
        assert bad.status_code == 400
        ok = api.post(reverse("accounts:mfa-disable"), {"password": STRONG_PW}, format="json")
        assert ok.status_code == 200
        verified_user.refresh_from_db()
        assert verified_user.mfa_enabled is False and verified_user.mfa_secret == ""


# ── Google OAuth (mocked) ───────────────────────────────────────────────────
@pytest.mark.django_db
class TestGoogleOAuth:
    def test_authorize_redirects_and_sets_cookie(self, api):
        r = api.get(reverse("accounts:google-authorize"))
        assert r.status_code == 302
        assert "accounts.google.com" in r["Location"]
        assert "g_oauth" in r.cookies

    def _state_from_location(self, location):
        import urllib.parse
        q = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        return q["state"][0]

    def test_callback_creates_user_and_oauth_account(self, api):
        authz = api.get(reverse("accounts:google-authorize"))
        state = self._state_from_location(authz["Location"])

        token_resp = mock.Mock(status_code=200)
        token_resp.json.return_value = {"access_token": "ya29.raw", "id_token": "x"}
        info_resp = mock.Mock(status_code=200)
        info_resp.json.return_value = {"sub": "g-123", "email": "G@Example.com", "name": "Gmail User"}

        with mock.patch("apps.accounts.views.requests.post", return_value=token_resp), \
             mock.patch("apps.accounts.views.requests.get", return_value=info_resp):
            r = api.get(reverse("accounts:google-callback"), {"code": "abc", "state": state})

        assert r.status_code == 302
        user = User.objects.get(email="g@example.com")
        assert user.is_verified is True
        acct = OAuthAccount.objects.get(provider="google", provider_user_id="g-123")
        # The raw Google token must NOT be persisted — only a reference.
        assert acct.access_token_ref == "google:g-123"
        assert "ya29.raw" not in acct.access_token_ref

    def test_callback_state_mismatch(self, api):
        api.get(reverse("accounts:google-authorize"))
        r = api.get(reverse("accounts:google-callback"), {"code": "abc", "state": "wrong"})
        assert r.status_code == 400


@pytest.mark.django_db
class TestMicrosoftOAuth:
    def _state(self, location):
        import urllib.parse
        return urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["state"][0]

    def test_authorize_redirects_and_sets_cookie(self, api):
        r = api.get(reverse("accounts:microsoft-authorize"))
        assert r.status_code == 302
        assert "login.microsoftonline.com" in r["Location"]
        assert "ms_oauth" in r.cookies

    def test_callback_creates_user_token_ref_only(self, api):
        authz = api.get(reverse("accounts:microsoft-authorize"))
        state = self._state(authz["Location"])
        token_resp = mock.Mock(status_code=200)
        token_resp.json.return_value = {"access_token": "ms.raw.token"}
        info_resp = mock.Mock(status_code=200)
        info_resp.json.return_value = {"sub": "ms-1", "email": "M@Example.com", "name": "MS User"}
        with mock.patch("apps.accounts.views.requests.post", return_value=token_resp), \
             mock.patch("apps.accounts.views.requests.get", return_value=info_resp):
            r = api.get(reverse("accounts:microsoft-callback"), {"code": "abc", "state": state})
        assert r.status_code == 302
        assert User.objects.filter(email="m@example.com").exists()
        acct = OAuthAccount.objects.get(provider="microsoft", provider_user_id="ms-1")
        assert acct.access_token_ref == "microsoft:ms-1"
        assert "ms.raw.token" not in acct.access_token_ref


@pytest.mark.django_db
class TestLoginLockout:
    @pytest.fixture(autouse=True)
    def _enable_lockout(self, settings):
        from django.core.cache import cache
        settings.LOGIN_LOCKOUT_ENABLED = True
        cache.clear()
        yield
        cache.clear()

    def test_lockout_after_threshold(self, api, verified_user):
        bad = {"email": verified_user.email, "password": "wrongpass!"}
        codes = [api.post(reverse("accounts:login"), bad, format="json").status_code for _ in range(6)]
        assert codes[:5] == [401, 401, 401, 401, 401]
        assert codes[5] == 429
        # Correct password is still refused while the lock is active.
        good = api.post(reverse("accounts:login"),
                        {"email": verified_user.email, "password": STRONG_PW}, format="json")
        assert good.status_code == 429

    def test_success_resets_counter(self, api, verified_user):
        for _ in range(3):
            api.post(reverse("accounts:login"),
                     {"email": verified_user.email, "password": "wrongpass!"}, format="json")
        ok = api.post(reverse("accounts:login"),
                      {"email": verified_user.email, "password": STRONG_PW}, format="json")
        assert ok.status_code == 200  # valid login clears the counter (no lock)
