"""Storage backends + signed URLs (PROJECT_HANDBOOK.md §24.1 / §24.5)."""
import time

import pytest

from apps.documents.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    get_storage_backend,
    sign_key,
    verify_signature,
)


def test_local_roundtrip(media_root):
    b = LocalStorageBackend()
    b.upload(b"hello", "ws/abc/file.txt")
    assert b.exists("ws/abc/file.txt")
    assert b.download("ws/abc/file.txt") == b"hello"
    b.delete("ws/abc/file.txt")
    assert not b.exists("ws/abc/file.txt")


def test_path_traversal_rejected(media_root):
    with pytest.raises(ValueError):
        LocalStorageBackend().upload(b"x", "../../etc/passwd")


def test_signature_roundtrip():
    expires = int(time.time()) + 60
    sig = sign_key("k/1", expires)
    assert verify_signature("k/1", expires, sig)


def test_expired_signature_fails():
    expires = int(time.time()) - 1
    assert not verify_signature("k/1", expires, sign_key("k/1", expires))


def test_tampered_signature_fails():
    expires = int(time.time()) + 60
    assert not verify_signature("k/1", expires, "deadbeef")


def test_signed_url_shape(media_root):
    url = LocalStorageBackend().generate_signed_url("ws/abc/file.txt", 300)
    assert url.startswith("/api/v1/documents/download/?")
    assert "sig=" in url and "expires=" in url


def test_get_backend_default_local():
    assert isinstance(get_storage_backend(), LocalStorageBackend)


def test_s3_requires_bucket(monkeypatch):
    monkeypatch.delenv("DOCUMENTS_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError):
        S3StorageBackend()


def test_get_backend_s3_selection(monkeypatch):
    monkeypatch.setenv("DOCUMENTS_STORAGE_BACKEND", "s3")
    monkeypatch.delenv("DOCUMENTS_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError):
        get_storage_backend()
