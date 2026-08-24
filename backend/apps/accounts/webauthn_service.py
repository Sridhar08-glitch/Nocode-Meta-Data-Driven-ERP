"""
WebAuthn / Passkey service (Phase 1.27).

Wraps the Yubico ``fido2`` server to register and authenticate passkeys, storing
credential descriptors in ``User.passkey_credentials`` (no new model — challenges are
cache-backed, credentials live on the user row). Passkeys act as an MFA factor at login.

Wire format: endpoints exchange the standard WebAuthn JSON (base64url) shape, so the
``webauthn_json_mapping`` fido2 feature is enabled at import.
"""
from __future__ import annotations

import enum
from collections.abc import Mapping

import fido2.features

# Endpoints speak the browser's WebAuthn JSON (base64url) wire format.
fido2.features.webauthn_json_mapping.enabled = True

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402
from fido2.server import Fido2Server  # noqa: E402
from fido2.utils import websafe_decode, websafe_encode  # noqa: E402
from fido2.webauthn import (  # noqa: E402
    AttestedCredentialData,
    AuthenticatorData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
)


class WebAuthnError(Exception):  # noqa: N818 — domain error
    pass


def _verify_origin(value: str) -> bool:
    # Pin the assertion/attestation origin to the configured frontend origin. fido2's
    # default only permits ``https://<rp_id>``, which excludes our dev origin + port.
    return value == settings.WEBAUTHN_ORIGIN


def _server() -> Fido2Server:
    rp = PublicKeyCredentialRpEntity(id=settings.WEBAUTHN_RP_ID, name=settings.WEBAUTHN_RP_NAME)
    return Fido2Server(rp, verify_origin=_verify_origin)


def origin() -> str:
    return settings.WEBAUTHN_ORIGIN


def _existing_credentials(user) -> list[AttestedCredentialData]:
    out = []
    for c in (user.passkey_credentials or []):
        try:
            out.append(AttestedCredentialData(websafe_decode(c["credential_data"])))
        except Exception:  # noqa: BLE001 — skip any corrupt descriptor, never crash auth
            continue
    return out


def _to_jsonable(obj):
    if isinstance(obj, bytes):
        return websafe_encode(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, Mapping):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list | tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def options_to_dict(options) -> dict:
    """Serialise fido2 credential options into a JSON-safe ``{"publicKey": {...}}`` payload."""
    return {"publicKey": _to_jsonable(dict(options)["publicKey"])}


# ── Registration ─────────────────────────────────────────────────────────────
def register_begin(user):
    """Return ``(options, state)`` for registering a new passkey for *user*."""
    options, state = _server().register_begin(
        PublicKeyCredentialUserEntity(
            id=str(user.id).encode(), name=user.email, display_name=user.display_name),
        credentials=_existing_credentials(user),
        user_verification="preferred",
        resident_key_requirement="discouraged",
    )
    return options, state


def register_complete(user, state, response, *, name: str = "") -> dict:
    """Verify a registration response and persist the credential descriptor."""
    try:
        auth_data = _server().register_complete(state, response)
    except Exception as exc:  # noqa: BLE001 — surface verification failure as a clean 400
        raise WebAuthnError(f"Passkey registration failed: {exc}") from exc

    cred = auth_data.credential_data
    cred_id = websafe_encode(cred.credential_id)
    creds = list(user.passkey_credentials or [])
    if any(c.get("id") == cred_id for c in creds):
        raise WebAuthnError("This passkey is already registered.")

    descriptor = {
        "id": cred_id,
        "credential_data": websafe_encode(bytes(cred)),
        "sign_count": int(getattr(auth_data, "counter", 0) or 0),
        "name": (name or "Passkey")[:100],
        "created_at": timezone.now().isoformat(),
        "last_used_at": None,
    }
    creds.append(descriptor)
    user.passkey_credentials = creds
    update_fields = ["passkey_credentials"]
    if not user.mfa_enabled:
        user.mfa_enabled = True  # a passkey is a second factor
        update_fields.append("mfa_enabled")
    user.save(update_fields=update_fields)
    return {"id": descriptor["id"], "name": descriptor["name"], "created_at": descriptor["created_at"]}


# ── Authentication ───────────────────────────────────────────────────────────
def authenticate_begin(user):
    """Return ``(options, state)`` for a passkey assertion challenge."""
    creds = _existing_credentials(user)
    if not creds:
        raise WebAuthnError("No passkeys registered for this account.")
    options, state = _server().authenticate_begin(creds, user_verification="preferred")
    return options, state


def authenticate_complete(user, state, response) -> dict:
    """Verify an assertion, enforce the signature counter, and update the credential."""
    creds = _existing_credentials(user)
    if not creds:
        raise WebAuthnError("No passkeys registered for this account.")
    try:
        matched = _server().authenticate_complete(state, creds, response)
    except Exception as exc:  # noqa: BLE001 — clean 401 on any verification failure
        raise WebAuthnError(f"Passkey authentication failed: {exc}") from exc

    used_id = websafe_encode(matched.credential_id)
    try:
        new_count = AuthenticatorData(
            websafe_decode(response["response"]["authenticatorData"])).counter
    except Exception as exc:  # noqa: BLE001
        raise WebAuthnError("Malformed authenticator data.") from exc

    stored = list(user.passkey_credentials or [])
    for c in stored:
        if c.get("id") == used_id:
            prev = int(c.get("sign_count", 0) or 0)
            # Counter regression (with at least one non-zero counter) signals a cloned
            # authenticator → reject. Counters of 0/0 are allowed (some authenticators
            # never increment).
            if new_count and prev and new_count <= prev:
                raise WebAuthnError("Passkey signature counter regression; possible cloned key.")
            c["sign_count"] = new_count
            c["last_used_at"] = timezone.now().isoformat()
            break
    user.passkey_credentials = stored
    user.save(update_fields=["passkey_credentials"])
    return {"id": used_id}


# ── Management ───────────────────────────────────────────────────────────────
def list_passkeys(user) -> list[dict]:
    return [{"id": c.get("id"), "name": c.get("name"), "created_at": c.get("created_at"),
             "last_used_at": c.get("last_used_at")}
            for c in (user.passkey_credentials or [])]


def delete_passkey(user, credential_id: str) -> bool:
    creds = list(user.passkey_credentials or [])
    remaining = [c for c in creds if c.get("id") != credential_id]
    if len(remaining) == len(creds):
        return False
    user.passkey_credentials = remaining
    update_fields = ["passkey_credentials"]
    # If passkeys were the only factor, disable MFA when the last one is removed.
    if not remaining and not user.mfa_secret:
        user.mfa_enabled = False
        update_fields.append("mfa_enabled")
    user.save(update_fields=update_fields)
    return True
