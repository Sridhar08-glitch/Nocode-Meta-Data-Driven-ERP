"""Documents REST API (PROJECT_HANDBOOK.md §24.4 / §24.5)."""
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Document
from apps.tenancy.models import Workspace

from .conftest import make_client

BASE = "/api/v1/documents"


def _upload(client, name="a.txt", content=b"hello", **data):
    f = SimpleUploadedFile(name, content, content_type="text/plain")
    return client.post(f"{BASE}/", {"file": f, **data}, format="multipart")


@pytest.mark.django_db
class TestDocumentApi:
    def test_upload_list_get(self, client):
        r = _upload(client)
        assert r.status_code == 201, r.content
        body = r.json()
        assert "storage_key" not in body          # never exposed
        assert body["checksum_sha256"]
        did = body["id"]
        assert client.get(f"{BASE}/").json()["count"] == 1
        assert client.get(f"{BASE}/{did}/").json()["name"] == "a.txt"

    def test_download_url_then_fetch_bytes(self, client):
        did = _upload(client, content=b"PAYLOAD").json()["id"]
        url = client.get(f"{BASE}/{did}/download-url/").json()["url"]
        # signed download endpoint is unauthenticated; fetch with a bare client
        from rest_framework.test import APIClient
        resp = APIClient().get(url)
        assert resp.status_code == 200
        assert resp.content == b"PAYLOAD"

    def test_download_url_bad_signature_404(self, client):
        did = _upload(client).json()["id"]
        url = client.get(f"{BASE}/{did}/download-url/").json()["url"]
        from rest_framework.test import APIClient
        assert APIClient().get(url + "tamper").status_code == 404

    def test_versions(self, client):
        did = _upload(client, content=b"v1").json()["id"]
        f = SimpleUploadedFile("a.txt", b"v2", content_type="text/plain")
        assert client.post(f"{BASE}/{did}/versions/", {"file": f},
                           format="multipart").json()["current_version"] == 2
        assert client.get(f"{BASE}/{did}/versions/").json()["count"] == 2

    def test_attach_detach(self, client):
        did = _upload(client).json()["id"]
        r = client.post(f"{BASE}/{did}/attach/",
                        {"entity_id": str(uuid.uuid4()), "record_id": str(uuid.uuid4())},
                        format="json")
        assert r.status_code == 200 and r.json()["record_id"]
        assert client.post(f"{BASE}/{did}/detach/").json()["record_id"] is None

    def test_delete_restore(self, client):
        did = _upload(client).json()["id"]
        assert client.delete(f"{BASE}/{did}/").status_code == 204
        assert Document.objects.get(id=did).is_deleted
        assert client.post(f"{BASE}/{did}/restore/").status_code == 200


@pytest.mark.django_db
class TestFolderApi:
    def test_folder_crud_and_contents(self, client):
        r = client.post(f"{BASE}/folders/", {"name": "HR"}, format="json")
        assert r.status_code == 201
        fid = r.json()["id"]
        assert r.json()["path"] == "/hr/"
        _upload(client, folder_id=fid)
        contents = client.get(f"{BASE}/folders/{fid}/contents/").json()
        assert len(contents["documents"]) == 1


@pytest.mark.django_db
class TestAuthz:
    def test_viewer_cannot_upload(self, ws):
        _, c = make_client(ws, "v@acme.com", role="viewer")
        assert _upload(c).status_code == 403

    def test_workspace_isolation(self, ws, client):
        did = _upload(client).json()["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        _, c2 = make_client(other, "x@other.com", role="admin")
        assert c2.get(f"{BASE}/{did}/").status_code == 404
