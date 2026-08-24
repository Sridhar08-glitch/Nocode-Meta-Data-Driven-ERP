"""DocumentService (PROJECT_HANDBOOK.md §24.2 / §24.5)."""
import hashlib
import uuid

import pytest

from apps.documents.models import Document, DocumentVersion
from apps.documents.services import DocumentError, DocumentService
from apps.documents.storage import get_storage_backend
from apps.eventstore.models import DomainEvent


@pytest.mark.django_db
class TestUpload:
    def test_upload_computes_checksum_and_stores_key(self, ws, user):
        data = b"file contents"
        doc = DocumentService.upload_document(
            file_obj=data, filename="Report 2024.pdf", uploaded_by=user.id,
            workspace_id=ws.id, mime_type="application/pdf")
        assert doc.checksum_sha256 == hashlib.sha256(data).hexdigest()
        assert doc.size_bytes == len(data)
        assert doc.storage_key and "/" in doc.storage_key
        # bytes actually landed in the backend
        assert get_storage_backend(ws.id).download(doc.storage_key) == data
        assert DocumentVersion.objects.filter(document_id=doc.id, version_number=1).exists()
        assert DomainEvent.objects.filter(
            aggregate_id=doc.id, event_type="document.uploaded").exists()

    def test_upload_with_attachment_emits_file_attached(self, ws, user):
        eid, rid = uuid.uuid4(), uuid.uuid4()
        doc = DocumentService.upload_document(
            file_obj=b"x", filename="a.txt", entity_id=eid, record_id=rid,
            uploaded_by=user.id, workspace_id=ws.id)
        assert DomainEvent.objects.filter(
            aggregate_id=doc.id, event_type="file.attached").exists()
        assert doc.entity_id == eid and doc.record_id == rid


@pytest.mark.django_db
class TestVersioning:
    def test_create_version_increments(self, ws, user):
        doc = DocumentService.upload_document(
            file_obj=b"v1", filename="a.txt", uploaded_by=user.id, workspace_id=ws.id)
        old_key = doc.storage_key
        doc = DocumentService.create_version(
            document_id=doc.id, file_obj=b"v2-bigger", workspace_id=ws.id,
            uploader_id=user.id, comment="second")
        assert doc.current_version == 2
        assert doc.storage_key != old_key
        assert get_storage_backend(ws.id).download(doc.storage_key) == b"v2-bigger"
        versions = DocumentService.list_versions(doc.id, ws.id)
        assert versions.count() == 2


@pytest.mark.django_db
class TestDownloadAndLifecycle:
    def test_download_url_signed_no_raw_path(self, ws, user):
        doc = DocumentService.upload_document(
            file_obj=b"x", filename="a.txt", uploaded_by=user.id, workspace_id=ws.id)
        url = DocumentService.get_download_url(doc.id, ws.id, requester_id=user.id)
        assert "sig=" in url

    def test_delete_and_restore(self, ws, user):
        doc = DocumentService.upload_document(
            file_obj=b"x", filename="a.txt", uploaded_by=user.id, workspace_id=ws.id)
        DocumentService.delete_document(doc.id, ws.id, user.id)
        assert Document.objects.get(id=doc.id).is_deleted
        DocumentService.restore_document(doc.id, ws.id, user.id)
        assert not Document.objects.get(id=doc.id).is_deleted

    def test_delete_attached_emits_file_removed(self, ws, user):
        doc = DocumentService.upload_document(
            file_obj=b"x", filename="a.txt", entity_id=uuid.uuid4(),
            record_id=uuid.uuid4(), uploaded_by=user.id, workspace_id=ws.id)
        DocumentService.delete_document(doc.id, ws.id, user.id)
        assert DomainEvent.objects.filter(
            aggregate_id=doc.id, event_type="file.removed").exists()

    def test_attach_detach(self, ws, user):
        doc = DocumentService.upload_document(
            file_obj=b"x", filename="a.txt", uploaded_by=user.id, workspace_id=ws.id)
        eid, rid = uuid.uuid4(), uuid.uuid4()
        DocumentService.attach(doc.id, entity_id=eid, record_id=rid, workspace_id=ws.id)
        assert Document.objects.get(id=doc.id).record_id == rid
        DocumentService.detach(doc.id, ws.id)
        assert Document.objects.get(id=doc.id).record_id is None


@pytest.mark.django_db
class TestFolders:
    def test_materialized_path(self, ws):
        root = DocumentService.create_folder(name="HR", workspace_id=ws.id)
        assert root.path == "/hr/"
        child = DocumentService.create_folder(name="2024", parent_id=root.id, workspace_id=ws.id)
        assert child.path == "/hr/2024/"

    def test_max_depth_enforced(self, ws):
        parent = None
        for i in range(10):  # depths 1..10 ok
            parent = DocumentService.create_folder(
                name=f"l{i}", parent_id=parent.id if parent else None, workspace_id=ws.id)
        with pytest.raises(DocumentError):
            DocumentService.create_folder(name="l10", parent_id=parent.id, workspace_id=ws.id)
