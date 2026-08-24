"""
Document storage backends (PROJECT_HANDBOOK.md §24.1).

A small protocol with a local-filesystem and an S3 implementation. Callers only
ever see a ``storage_key`` (never a raw path/URL); downloads go through a
**signed, expiring URL**. Credentials/bucket names come from the environment —
never the database.

Local signed URLs are a relative API path + HMAC-SHA256 signature over
``key:expires`` (verified by the download view). S3 uses boto3 presigned URLs
(boto3 imported lazily so it is only required when S3 is actually selected).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path

from django.conf import settings

DOCUMENTS_SUBDIR = "documents"


def _signing_key() -> bytes:
    return settings.SECRET_KEY.encode()


def sign_key(storage_key: str, expires: int) -> str:
    msg = f"{storage_key}:{expires}".encode()
    return hmac.new(_signing_key(), msg, hashlib.sha256).hexdigest()


def verify_signature(storage_key: str, expires: int, signature: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = sign_key(storage_key, expires)
    return hmac.compare_digest(expected, signature or "")


class LocalStorageBackend:
    """Stores bytes under ``MEDIA_ROOT/documents/<storage_key>``."""

    name = "local"

    def _path(self, storage_key: str) -> Path:
        root = Path(settings.MEDIA_ROOT) / DOCUMENTS_SUBDIR
        full = (root / storage_key).resolve()
        if not str(full).startswith(str(root.resolve())):
            raise ValueError("Invalid storage key (path traversal)")
        return full

    def upload(self, data: bytes, storage_key: str) -> str:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return storage_key

    def download(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        if path.exists():
            path.unlink()

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).exists()

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        expires = int(time.time()) + int(expires_in)
        sig = sign_key(storage_key, expires)
        from urllib.parse import urlencode
        qs = urlencode({"key": storage_key, "expires": expires, "sig": sig})
        return f"/api/v1/documents/download/?{qs}"


class S3StorageBackend:
    """Stores bytes in an S3 bucket; presigned URLs for download.

    Bucket from ``DOCUMENTS_S3_BUCKET``; credentials from the standard AWS env
    vars — never the DB. boto3 is imported lazily.
    """

    name = "s3"

    def __init__(self):
        self.bucket = os.environ.get("DOCUMENTS_S3_BUCKET")
        if not self.bucket:
            raise RuntimeError("DOCUMENTS_S3_BUCKET is not configured")

    def _client(self):
        import boto3  # lazy — only required when S3 is selected
        return boto3.client("s3", region_name=os.environ.get("AWS_REGION"))

    def upload(self, data: bytes, storage_key: str) -> str:
        self._client().put_object(Bucket=self.bucket, Key=storage_key, Body=data)
        return storage_key

    def download(self, storage_key: str) -> bytes:
        obj = self._client().get_object(Bucket=self.bucket, Key=storage_key)
        return obj["Body"].read()

    def delete(self, storage_key: str) -> None:
        self._client().delete_object(Bucket=self.bucket, Key=storage_key)

    def exists(self, storage_key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self._client().head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError:
            return False

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        return self._client().generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=int(expires_in))


def get_storage_backend(workspace_id=None):
    """Return the configured backend (``DOCUMENTS_STORAGE_BACKEND``; default local)."""
    backend = os.environ.get("DOCUMENTS_STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()
