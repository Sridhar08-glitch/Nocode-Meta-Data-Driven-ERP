"""
Documents REST API (PROJECT_HANDBOOK.md §24.4).

Workspace-scoped folders + documents, multipart upload, versioning, signed
download URLs, and record attachments. Writes are role-gated (owner/admin/member);
the signed local-download endpoint is unauthenticated but validates an
HMAC signature + expiry (the URL itself is the capability).
"""
import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document, DocumentFolder
from .serializers import (
    DocumentFolderSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
)
from .services import DocumentError, DocumentNotFound, DocumentService
from .storage import LocalStorageBackend, verify_signature

_WRITE_ROLES = {"owner", "admin", "member"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _run(fn):
    try:
        return fn()
    except DocumentNotFound as exc:
        raise NotFound(str(exc)) from exc
    except DocumentError as exc:
        raise ValidationError(str(exc)) from exc


# ── folders ───────────────────────────────────────────────────────────────────
class FolderListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = DocumentFolder.objects.filter(
            workspace_id=_ws(request), deleted_at__isnull=True).order_by("path")
        return Response({"results": DocumentFolderSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_write(request)
        name = request.data.get("name")
        if not name:
            raise ValidationError("name is required")
        folder = _run(lambda: DocumentService.create_folder(
            name=name, parent_id=request.data.get("parent_id"), workspace_id=_ws(request)))
        return Response(DocumentFolderSerializer(folder).data, status=status.HTTP_201_CREATED)


class FolderDetailView(APIView):
    def _get(self, request, pk):
        f = DocumentFolder.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if f is None:
            raise NotFound("Folder not found")
        return f

    def get(self, request, pk):
        _member(request)
        return Response(DocumentFolderSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        folder = self._get(request, pk)
        if "name" in request.data:
            folder.name = request.data["name"][:255]
            folder.save(update_fields=["name", "updated_at"])
        return Response(DocumentFolderSerializer(folder).data)

    def delete(self, request, pk):
        _require_write(request)
        self._get(request, pk).soft_delete(_member(request).user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FolderContentsView(APIView):
    def get(self, request, pk):
        _member(request)
        folders, docs = DocumentService.folder_contents(pk, _ws(request))
        return Response({
            "folders": DocumentFolderSerializer(folders, many=True).data,
            "documents": DocumentSerializer(docs, many=True).data})


# ── documents ─────────────────────────────────────────────────────────────────
class DocumentListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = Document.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        if request.query_params.get("folder_id"):
            qs = qs.filter(folder_id=request.query_params["folder_id"])
        if request.query_params.get("record_id"):
            qs = qs.filter(record_id=request.query_params["record_id"])
        if request.query_params.get("entity_id"):
            qs = qs.filter(entity_id=request.query_params["entity_id"])
        qs = qs.order_by("-created_at")[:200]
        return Response({"results": DocumentSerializer(qs, many=True).data, "count": len(qs)})

    def post(self, request):
        member = _require_write(request)
        file_obj = request.FILES.get("file")
        if file_obj is None:
            raise ParseError("multipart 'file' is required")
        doc = DocumentService.upload_document(
            file_obj=file_obj, filename=file_obj.name,
            folder_id=request.data.get("folder_id"),
            entity_id=request.data.get("entity_id"),
            record_id=request.data.get("record_id"),
            uploaded_by=member.user_id, workspace_id=_ws(request),
            mime_type=getattr(file_obj, "content_type", "") or "")
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    def _get(self, request, pk, include_deleted=False):
        try:
            return DocumentService._get(pk, _ws(request), include_deleted=include_deleted)
        except DocumentNotFound as exc:
            raise NotFound(str(exc)) from exc

    def get(self, request, pk):
        _member(request)
        return Response(DocumentSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        doc = self._get(request, pk)
        for field in ("name", "description", "folder_id", "is_public"):
            if field in request.data:
                setattr(doc, field, request.data[field])
        doc.save()
        return Response(DocumentSerializer(doc).data)

    def delete(self, request, pk):
        member = _require_write(request)
        _run(lambda: DocumentService.delete_document(pk, _ws(request), member.user_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentRestoreView(APIView):
    def post(self, request, pk):
        member = _require_write(request)
        doc = _run(lambda: DocumentService.restore_document(pk, _ws(request), member.user_id))
        return Response(DocumentSerializer(doc).data)


class DocumentDownloadUrlView(APIView):
    def get(self, request, pk):
        member = _member(request)
        try:
            expires_in = min(int(request.query_params.get("expires_in", 300)), 3600)
        except (TypeError, ValueError) as exc:
            raise ParseError("expires_in must be an integer") from exc
        url = _run(lambda: DocumentService.get_download_url(
            pk, _ws(request), requester_id=member.user_id, expires_in=expires_in))
        return Response({"url": url, "expires_in": expires_in})


class DocumentVersionsView(APIView):
    def get(self, request, pk):
        _member(request)
        versions = _run(lambda: DocumentService.list_versions(pk, _ws(request)))
        return Response({"results": DocumentVersionSerializer(versions, many=True).data,
                         "count": versions.count()})

    def post(self, request, pk):
        member = _require_write(request)
        file_obj = request.FILES.get("file")
        if file_obj is None:
            raise ParseError("multipart 'file' is required")
        doc = _run(lambda: DocumentService.create_version(
            document_id=pk, file_obj=file_obj, workspace_id=_ws(request),
            uploader_id=member.user_id, comment=request.data.get("comment", "")))
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentAttachView(APIView):
    def post(self, request, pk):
        member = _require_write(request)
        entity_id = request.data.get("entity_id")
        record_id = request.data.get("record_id")
        if not entity_id or not record_id:
            raise ValidationError("entity_id and record_id are required")
        doc = _run(lambda: DocumentService.attach(
            pk, entity_id=entity_id, record_id=record_id, workspace_id=_ws(request),
            actor_id=member.user_id))
        return Response(DocumentSerializer(doc).data)


class DocumentDetachView(APIView):
    def post(self, request, pk):
        member = _require_write(request)
        doc = _run(lambda: DocumentService.detach(pk, _ws(request), member.user_id))
        return Response(DocumentSerializer(doc).data)


class SignedDownloadView(APIView):
    """Serve local-backend bytes from a signed, expiring URL (the URL is the capability)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        key = request.query_params.get("key", "")
        sig = request.query_params.get("sig", "")
        try:
            expires = int(request.query_params.get("expires", 0))
        except (TypeError, ValueError):
            raise NotFound("Invalid link") from None
        if not verify_signature(key, expires, sig):
            raise NotFound("Link expired or invalid")
        try:
            data = LocalStorageBackend().download(key)
        except (FileNotFoundError, ValueError) as exc:
            raise NotFound("File not found") from exc
        resp = HttpResponse(data, content_type="application/octet-stream")
        resp["Content-Disposition"] = f'attachment; filename="{key.split("/")[-1]}"'
        return resp
