"""
DocumentService (PROJECT_HANDBOOK.md §24.2).

Uploads compute a SHA-256 checksum and store bytes via a pluggable
:mod:`~apps.documents.storage` backend under a generated ``storage_key`` — the DB
only ever holds the key, never a raw path/URL. Versions are immutable
``DocumentVersion`` rows. Downloads are short-lived **signed URLs**. Record
attachments emit ``file.attached`` / ``file.removed`` events that surface on the
activity feed (Phase 1.14).
"""
from __future__ import annotations

import hashlib
import os
import uuid

from django.utils.text import slugify

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import Document, DocumentFolder, DocumentVersion
from .storage import get_storage_backend

MAX_FOLDER_DEPTH = 10


class DocumentError(Exception):  # noqa: N818 — domain error
    pass


class DocumentNotFound(Exception):  # noqa: N818
    pass


def _read_bytes(file_obj) -> bytes:
    if hasattr(file_obj, "read"):
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return file_obj.read()
    return bytes(file_obj)


def _safe_name(filename: str) -> str:
    filename = (filename or "file").replace("\\", "/").split("/")[-1]
    stem, dot, ext = filename.rpartition(".")
    base = slugify(stem or filename) or "file"
    ext = slugify(ext) if dot else ""
    return f"{base}.{ext}" if ext else base


def _extension(filename: str) -> str:
    _, dot, ext = (filename or "").rpartition(".")
    return ext.lower() if dot else ""


def _emit(document, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=document.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=document.workspace_id,
        aggregate_type="document", aggregate_id=document.id, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


class DocumentService:
    @staticmethod
    def upload_document(*, file_obj, filename, folder_id=None, entity_id=None,
                        record_id=None, uploaded_by=None, workspace_id, mime_type=""):
        data = _read_bytes(file_obj)
        checksum = hashlib.sha256(data).hexdigest()
        backend = get_storage_backend(workspace_id)
        ws_hex8 = uuid.UUID(str(workspace_id)).hex[:8]
        storage_key = f"{ws_hex8}/{uuid.uuid4().hex}/{_safe_name(filename)}"
        backend.upload(data, storage_key)

        doc = Document.objects.create(
            workspace_id=workspace_id, folder_id=folder_id, name=filename[:500],
            mime_type=mime_type[:127], extension=_extension(filename),
            size_bytes=len(data), storage_key=storage_key, storage_backend=backend.name,
            checksum_sha256=checksum, status="ready", current_version=1, is_latest=True,
            entity_id=entity_id, record_id=record_id, created_by=uploaded_by)
        DocumentVersion.objects.create(
            document_id=doc.id, workspace_id=workspace_id, version_number=1,
            storage_key=storage_key, size_bytes=len(data), checksum_sha256=checksum,
            uploaded_by=uploaded_by)
        _emit(doc, "document.uploaded",
              {"name": doc.name, "size_bytes": doc.size_bytes}, uploaded_by)
        if entity_id and record_id:
            _emit(doc, "file.attached",
                  {"entity_id": str(entity_id), "record_id": str(record_id),
                   "document_id": str(doc.id)}, uploaded_by)
        if os.environ.get("DOCUMENTS_AV_SCAN"):
            from .tasks import scan_document_av
            scan_document_av.delay(str(doc.id))
        return doc

    @staticmethod
    def _get(document_id, workspace_id, *, include_deleted=False) -> Document:
        doc = Document.objects.filter(id=document_id, workspace_id=workspace_id).first()
        if doc is None or (doc.is_deleted and not include_deleted):
            raise DocumentNotFound("Document not found")
        return doc

    @staticmethod
    def create_version(*, document_id, file_obj, workspace_id, uploader_id=None,
                       comment=""):
        doc = DocumentService._get(document_id, workspace_id)
        data = _read_bytes(file_obj)
        checksum = hashlib.sha256(data).hexdigest()
        backend = get_storage_backend(workspace_id)
        ws_hex8 = uuid.UUID(str(workspace_id)).hex[:8]
        storage_key = f"{ws_hex8}/{uuid.uuid4().hex}/{_safe_name(doc.name)}"
        backend.upload(data, storage_key)
        new_version = doc.current_version + 1
        DocumentVersion.objects.create(
            document_id=doc.id, workspace_id=workspace_id, version_number=new_version,
            storage_key=storage_key, size_bytes=len(data), checksum_sha256=checksum,
            uploaded_by=uploader_id, comment=comment[:500])
        doc.storage_key = storage_key
        doc.size_bytes = len(data)
        doc.checksum_sha256 = checksum
        doc.current_version = new_version
        doc.save(update_fields=["storage_key", "size_bytes", "checksum_sha256",
                                "current_version", "updated_at"])
        _emit(doc, "document.versioned", {"version_number": new_version}, uploader_id)
        return doc

    @staticmethod
    def list_versions(document_id, workspace_id):
        DocumentService._get(document_id, workspace_id, include_deleted=True)
        return DocumentVersion.objects.filter(
            document_id=document_id, workspace_id=workspace_id).order_by("-version_number")

    @staticmethod
    def get_download_url(document_id, workspace_id, *, requester_id=None, expires_in=300):
        doc = DocumentService._get(document_id, workspace_id)
        backend = get_storage_backend(workspace_id)
        return backend.generate_signed_url(doc.storage_key, expires_in)

    @staticmethod
    def move_document(document_id, target_folder_id, workspace_id, actor_id=None):
        doc = DocumentService._get(document_id, workspace_id)
        doc.folder_id = target_folder_id
        doc.save(update_fields=["folder_id", "updated_at"])
        _emit(doc, "document.moved", {"folder_id": str(target_folder_id)
                                      if target_folder_id else None}, actor_id)
        return doc

    @staticmethod
    def delete_document(document_id, workspace_id, actor_id=None):
        doc = DocumentService._get(document_id, workspace_id)
        doc.soft_delete(actor_id)
        _emit(doc, "document.deleted", {}, actor_id)
        if doc.entity_id and doc.record_id:
            _emit(doc, "file.removed",
                  {"entity_id": str(doc.entity_id), "record_id": str(doc.record_id),
                   "document_id": str(doc.id)}, actor_id)
        return doc

    @staticmethod
    def restore_document(document_id, workspace_id, actor_id=None):
        doc = DocumentService._get(document_id, workspace_id, include_deleted=True)
        doc.restore()
        _emit(doc, "document.restored", {}, actor_id)
        return doc

    @staticmethod
    def attach(document_id, *, entity_id, record_id, workspace_id, actor_id=None):
        doc = DocumentService._get(document_id, workspace_id)
        doc.entity_id = entity_id
        doc.record_id = record_id
        doc.save(update_fields=["entity_id", "record_id", "updated_at"])
        _emit(doc, "file.attached",
              {"entity_id": str(entity_id), "record_id": str(record_id),
               "document_id": str(doc.id)}, actor_id)
        return doc

    @staticmethod
    def detach(document_id, workspace_id, actor_id=None):
        doc = DocumentService._get(document_id, workspace_id)
        old_entity, old_record = doc.entity_id, doc.record_id
        doc.entity_id = None
        doc.record_id = None
        doc.save(update_fields=["entity_id", "record_id", "updated_at"])
        if old_entity and old_record:
            _emit(doc, "file.removed",
                  {"entity_id": str(old_entity), "record_id": str(old_record),
                   "document_id": str(doc.id)}, actor_id)
        return doc

    @staticmethod
    def create_folder(*, name, parent_id=None, workspace_id):
        parent = None
        if parent_id:
            parent = DocumentFolder.objects.filter(
                id=parent_id, workspace_id=workspace_id).first()
            if parent is None:
                raise DocumentError("Parent folder not found")
        base_path = (parent.path if parent else "/") or "/"
        if not base_path.endswith("/"):
            base_path += "/"
        path = f"{base_path}{slugify(name) or 'folder'}/"
        if path.strip("/").count("/") + 1 > MAX_FOLDER_DEPTH:
            raise DocumentError(f"Folder depth exceeds {MAX_FOLDER_DEPTH}")
        return DocumentFolder.objects.create(
            workspace_id=workspace_id, name=name[:255], parent_id=parent_id, path=path)

    @staticmethod
    def folder_contents(folder_id, workspace_id):
        folders = DocumentFolder.objects.filter(
            workspace_id=workspace_id, parent_id=folder_id, deleted_at__isnull=True)
        docs = Document.objects.filter(
            workspace_id=workspace_id, folder_id=folder_id, deleted_at__isnull=True)
        return folders, docs
