"""
Cryptographic helpers for authentication.

- Fernet symmetric encryption for at-rest secrets (TOTP MFA secrets).
- SHA-256 hashing for opaque tokens (email verification, password reset, API keys).

The Fernet key is derived from ``settings.ENCRYPTION_KEY`` so the configured value
may be a human passphrase rather than a raw 32-byte urlsafe-base64 key.
"""
import base64
import hashlib
import secrets

from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet() -> Fernet:
    """Return a Fernet instance keyed off ``settings.ENCRYPTION_KEY``."""
    digest = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt *plaintext* and return a urlsafe token string."""
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`."""
    return get_fernet().decrypt(ciphertext.encode()).decode()


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of *raw_token* (for at-rest token storage)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_token(nbytes: int = 32) -> str:
    """Return a cryptographically-secure urlsafe token string."""
    return secrets.token_urlsafe(nbytes)
