"""
Passkey / WebAuthn tests (Phase 1.27).

Drives a software authenticator (``soft_webauthn``) end-to-end through the real HTTP
endpoints. The fido2 ``webauthn_json_mapping`` feature is enabled by importing the
service, so endpoints exchange the base64url JSON wire format the browser uses.
"""
import pytest
from django.conf import settings
from fido2.utils import websafe_decode, websafe_encode
from rest_framework.test import APIClient
from soft_webauthn import SoftWebauthnDevice

from apps.accounts import tokens, webauthn_service  # noqa: F401 — import enables fido2 feature
from apps.accounts.models import User

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/auth"
ORIGIN = settings.WEBAUTHN_ORIGIN
RP_ID = settings.WEBAUTHN_RP_ID


@pytest.fixture
def user(db):
    return User.objects.create_user(email="pk@example.com", password=PW,
                                    full_name="Pat Key", is_verified=True)


def _auth_client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
    return c


def _reg_wire(att):
    return {
        "id": websafe_encode(att["rawId"]),
        "rawId": websafe_encode(att["rawId"]),
        "type": att["type"],
        "clientExtensionResults": {},
        "response": {
            "clientDataJSON": websafe_encode(att["response"]["clientDataJSON"]),
            "attestationObject": websafe_encode(att["response"]["attestationObject"]),
        },
    }


def _auth_wire(asr):
    uh = asr["response"]["userHandle"]
    return {
        "id": websafe_encode(asr["rawId"]),
        "rawId": websafe_encode(asr["rawId"]),
        "type": asr["type"],
        "clientExtensionResults": {},
        "response": {
            "authenticatorData": websafe_encode(asr["response"]["authenticatorData"]),
            "clientDataJSON": websafe_encode(asr["response"]["clientDataJSON"]),
            "signature": websafe_encode(asr["response"]["signature"]),
            "userHandle": websafe_encode(uh) if uh else None,
        },
    }


def _device_create_opts(public_key):
    """Build the dict SoftWebauthnDevice.create expects (challenge/user.id as bytes)."""
    return {"publicKey": {
        "rp": {"id": public_key["rp"]["id"]},
        "user": {"id": websafe_decode(public_key["user"]["id"])},
        "challenge": websafe_decode(public_key["challenge"]),
        "pubKeyCredParams": [{"alg": -7, "type": "public-key"}],
    }}


def _device_get_opts(public_key):
    return {"publicKey": {"rpId": public_key["rpId"], "challenge": websafe_decode(public_key["challenge"])}}


def _register_passkey(user, device, name="My Key"):
    client = _auth_client(user)
    begin = client.post(f"{BASE}/mfa/passkey/register/begin/", {}, format="json")
    assert begin.status_code == 200, begin.data
    att = device.create(_device_create_opts(begin.data["publicKey"]), ORIGIN)
    return client.post(f"{BASE}/mfa/passkey/register/complete/",
                       {"credential": _reg_wire(att), "name": name}, format="json")


@pytest.mark.django_db
class TestPasskeyRegistration:
    def test_register_happy_path(self, user):
        device = SoftWebauthnDevice()
        r = _register_passkey(user, device, name="YubiKey")
        assert r.status_code == 201, r.data
        user.refresh_from_db()
        assert len(user.passkey_credentials) == 1
        assert user.passkey_credentials[0]["name"] == "YubiKey"
        assert user.mfa_enabled is True  # passkey is a second factor

    def test_register_begin_requires_auth(self, user):
        r = APIClient().post(f"{BASE}/mfa/passkey/register/begin/", {}, format="json")
        assert r.status_code in (401, 403)

    def test_register_complete_without_challenge_400(self, user):
        # No begin call → no cached challenge.
        r = _auth_client(user).post(f"{BASE}/mfa/passkey/register/complete/",
                                    {"credential": {"id": "x", "rawId": "x", "type": "public-key",
                                                    "response": {}}},
                                    format="json")
        assert r.status_code == 400

    def test_list_and_delete_passkey(self, user):
        device = SoftWebauthnDevice()
        _register_passkey(user, device)
        client = _auth_client(user)
        lr = client.get(f"{BASE}/mfa/passkey/")
        assert lr.status_code == 200 and len(lr.data) == 1
        cred_id = lr.data[0]["id"]
        dr = client.delete(f"{BASE}/mfa/passkey/{cred_id}/")
        assert dr.status_code == 204
        user.refresh_from_db()
        assert user.passkey_credentials == []
        assert user.mfa_enabled is False  # last factor removed


@pytest.mark.django_db
class TestPasskeyAuthentication:
    def _challenge_login(self, user):
        """Password login that returns an mfa challenge token (mfa is enabled by a passkey)."""
        r = APIClient().post(f"{BASE}/login/", {"email": user.email, "password": PW}, format="json")
        assert r.status_code == 200 and r.data.get("mfa_required") is True
        return r.data["mfa_token"]

    def test_authenticate_happy_path(self, user):
        device = SoftWebauthnDevice()
        _register_passkey(user, device)
        mfa_token = self._challenge_login(user)

        anon = APIClient()
        begin = anon.post(f"{BASE}/mfa/passkey/authenticate/begin/",
                          {"mfa_token": mfa_token}, format="json")
        assert begin.status_code == 200, begin.data
        asr = device.get(_device_get_opts(begin.data["publicKey"]), ORIGIN)
        complete = anon.post(f"{BASE}/mfa/passkey/authenticate/complete/",
                             {"mfa_token": mfa_token, "credential": _auth_wire(asr)}, format="json")
        assert complete.status_code == 200, complete.data
        assert "access" in complete.data and "refresh" in complete.data

    def test_counter_regression_rejected(self, user):
        device = SoftWebauthnDevice()
        _register_passkey(user, device)
        # Simulate a previously-recorded high signature counter (cloned-key detection).
        user.refresh_from_db()
        user.passkey_credentials[0]["sign_count"] = 1000
        user.save(update_fields=["passkey_credentials"])

        mfa_token = self._challenge_login(user)
        anon = APIClient()
        begin = anon.post(f"{BASE}/mfa/passkey/authenticate/begin/",
                          {"mfa_token": mfa_token}, format="json")
        asr = device.get(_device_get_opts(begin.data["publicKey"]), ORIGIN)  # low counter
        complete = anon.post(f"{BASE}/mfa/passkey/authenticate/complete/",
                             {"mfa_token": mfa_token, "credential": _auth_wire(asr)}, format="json")
        assert complete.status_code == 401

    def test_tampered_assertion_rejected(self, user):
        device = SoftWebauthnDevice()
        _register_passkey(user, device)
        mfa_token = self._challenge_login(user)
        anon = APIClient()
        begin = anon.post(f"{BASE}/mfa/passkey/authenticate/begin/",
                          {"mfa_token": mfa_token}, format="json")
        asr = device.get(_device_get_opts(begin.data["publicKey"]), ORIGIN)
        wire = _auth_wire(asr)
        wire["response"]["signature"] = websafe_encode(b"\x00" * 64)  # corrupt signature
        complete = anon.post(f"{BASE}/mfa/passkey/authenticate/complete/",
                             {"mfa_token": mfa_token, "credential": wire}, format="json")
        assert complete.status_code == 401

    def test_authenticate_begin_invalid_token_401(self, user):
        r = APIClient().post(f"{BASE}/mfa/passkey/authenticate/begin/",
                             {"mfa_token": "not-a-token"}, format="json")
        assert r.status_code == 401
